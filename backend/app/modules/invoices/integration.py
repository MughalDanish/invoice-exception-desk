from typing import Annotated

from fastapi import APIRouter, Depends, File, Header, Request, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from app.core.auth import require_integration
from app.db.models import InvoiceStatus, Severity, Source, ValidationResult
from app.modules.extraction.adapters import Extractor, get_extractor
from app.modules.extraction.processing import process_invoice
from app.modules.invoices.routes import Db
from app.modules.invoices.service import ingest_file
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
