import uuid
from decimal import Decimal, InvalidOperation, localcontext
from typing import Annotated

from fastapi import APIRouter, Depends, File, Header, Request, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from app.core.auth import require_integration
from app.db.models import InvoiceStatus, ProcessingAttempt, Severity, Source, ValidationResult
from app.modules.extraction.adapters import Extractor, get_extractor
from app.modules.extraction.processing import process_invoice
from app.modules.invoices.routes import Db
from app.modules.invoices.service import get_invoice, ingest_file
from app.modules.invoices.storage import validate_file

router = APIRouter(prefix="/api/v1/integrations/n8n", tags=["Integration"])


@router.post("/invoices")
async def intake(
    request: Request,
    session: Db,
    actor: Annotated[str, Depends(require_integration)],
    extractor: Annotated[Extractor, Depends(get_extractor)],
    idempotency_key: Annotated[
        str, Header(min_length=1, max_length=255, pattern=r"^[A-Za-z0-9._:@/-]+$")
    ],
    file: UploadFile = File(),
):
    settings = request.app.state.settings
    try:
        content = await file.read(settings.max_upload_bytes + 1)
        validated = await run_in_threadpool(
            validate_file,
            file.filename or "",
            file.content_type,
            content,
            settings.max_upload_bytes,
        )
        invoice, duplicate = await run_in_threadpool(
            ingest_file,
            session,
            validated,
            settings.storage_dir,
            actor,
            Source.gmail,
            idempotency_key,
        )
    finally:
        await file.close()
    attempt = None
    # A retry never modifies human-reviewed or terminal data. Failed extraction is
    # deliberately retried only by the operator, not by repeated email deliveries.
    if invoice.status in (InvoiceStatus.RECEIVED, InvoiceStatus.EXTRACTING):
        invoice, attempt = await run_in_threadpool(
            process_invoice, session, invoice.id, settings, extractor, actor
        )
    codes = list(
        session.scalars(
            select(ValidationResult.rule_code).where(
                ValidationResult.invoice_id == invoice.id,
                ValidationResult.run_id == invoice.validation_run_id,
                ValidationResult.revision == invoice.revision,
                ValidationResult.passed.is_(False),
                ValidationResult.severity == Severity.BLOCKER,
            )
        )
    )
    return JSONResponse(
        status_code=202
        if invoice.status == InvoiceStatus.EXTRACTING
        else (200 if duplicate else 201),
        content={
            "invoice_id": str(invoice.id),
            "status": invoice.status.value,
            "duplicate": duplicate,
            "blocker_codes": codes,
            "error_code": attempt.error_code if attempt else None,
        },
    )


def notification_rule(rule):
    """Present recorded validation amounts; never modify invoice data or rule outcomes."""
    result = {
        "rule_code": rule.rule_code,
        "severity": rule.severity.value,
        "passed": rule.passed,
        "message": rule.message,
    }
    if rule.rule_code != "TOTAL_MISMATCH" or rule.passed:
        return result
    expected = rule.expected.get("amount") if isinstance(rule.expected, dict) else None
    observed = rule.observed.get("amount") if isinstance(rule.observed, dict) else None
    if not all(isinstance(v, str) and len(v) <= 80 for v in (expected, observed)):
        return result
    try:
        expected_decimal, observed_decimal = Decimal(expected), Decimal(observed)
        if not expected_decimal.is_finite() or not observed_decimal.is_finite():
            return result
        with localcontext() as context:
            context.prec = 192
            difference = format(observed_decimal - expected_decimal, "f")
    except InvalidOperation:
        return result
    result.update(expected_amount=expected, observed_amount=observed, difference_amount=difference)
    return result


@router.get("/invoices/{invoice_id}")
def notification_detail(
    invoice_id: uuid.UUID, session: Db, actor: Annotated[str, Depends(require_integration)]
):
    """Read-only notification projection; no document, credential, or approval payloads."""
    invoice = get_invoice(session, invoice_id)
    data = invoice.current_data or {}
    attempt = session.scalar(
        select(ProcessingAttempt)
        .where(ProcessingAttempt.invoice_id == invoice.id)
        .order_by(ProcessingAttempt.ordinal.desc())
        .limit(1)
    )
    rules = session.scalars(
        select(ValidationResult).where(
            ValidationResult.invoice_id == invoice.id,
            ValidationResult.revision == invoice.revision,
            ValidationResult.run_id == invoice.validation_run_id,
        )
    ).all()
    return {
        "invoice_id": str(invoice.id),
        "status": invoice.status.value,
        "source": invoice.source.value,
        "invoice_number": data.get("invoice_number"),
        "supplier_name": data.get("vendor_name"),
        "invoice_date": data.get("invoice_date"),
        "due_date": data.get("due_date"),
        "total": data.get("total"),
        "currency": data.get("currency"),
        "error_code": attempt.error_code if attempt else None,
        "validations": [notification_rule(r) for r in rules],
    }
