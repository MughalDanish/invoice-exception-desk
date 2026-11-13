import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.auth import require_operator
from app.db.models import (
    AuditEvent,
    Invoice,
    InvoiceReview,
    InvoiceStatus,
    LedgerEntry,
    ProcessingAttempt,
    Severity,
    ValidationResult,
    Vendor,
)
from app.db.session import get_session
from app.modules.approvals.schemas import (
    CorrectionRequest,
    ReviewRequest,
    RevisionRequest,
    VendorCreate,
)
from app.modules.approvals.service import (
    correct_invoice,
    create_vendor,
    revalidate_invoice,
    review_invoice,
)
from app.modules.extraction.adapters import Extractor, get_extractor
from app.modules.extraction.processing import process_invoice
from app.modules.invoices.schemas import (
    AuditSummary,
    InvoiceActionResult,
    InvoiceDetail,
    InvoicePage,
    InvoiceSummary,
    ProcessingResult,
    UploadResult,
    VendorSummary,
    action_result,
)
from app.modules.invoices.service import get_invoice, ingest_file
from app.modules.invoices.storage import resolve_private_file, validate_file
from app.modules.ledger.export import export_csv
from app.modules.ledger.schemas import LedgerPage, LedgerSummary, ledger_summary
from app.modules.ledger.service import post_invoice

router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_operator)])
Db = Annotated[Session, Depends(get_session)]
Operator = Annotated[str, Depends(require_operator)]


@router.post("/invoices/upload", response_model=UploadResult, status_code=201)
async def upload(request: Request, session: Db, actor: Operator, file: UploadFile = File()):
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
        )
    finally:
        await file.close()
    result = UploadResult(invoice_id=invoice.id, status=invoice.status, duplicate=duplicate)
    return JSONResponse(
        status_code=200 if duplicate else 201, content=result.model_dump(mode="json")
    )


@router.get("/invoices", response_model=InvoicePage)
def list_invoices(
    session: Db,
    status: InvoiceStatus | None = None,
    search: str = Query(default="", max_length=200),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=25, ge=1, le=100),
    issue: str = Query(default="", max_length=80),
):
    conditions = []
    if status is not None:
        conditions.append(Invoice.status == status)
    if issue:
        conditions.append(
            select(ValidationResult.id)
            .where(
                ValidationResult.invoice_id == Invoice.id,
                ValidationResult.run_id == Invoice.validation_run_id,
                ValidationResult.revision == Invoice.revision,
                ValidationResult.passed.is_(False),
                ValidationResult.rule_code == issue,
            )
            .exists()
        )
    if search:
        # Search characters such as % and _ are literal, not SQL wildcards.
        conditions.append(
            or_(
                Invoice.filename.icontains(search, autoescape=True),
                Invoice.current_data["vendor_name"].astext.icontains(search, autoescape=True),
                Invoice.current_data["invoice_number"].astext.icontains(search, autoescape=True),
            )
        )
    total = session.scalar(select(func.count()).select_from(Invoice).where(*conditions))
    invoices = session.scalars(
        select(Invoice)
        .where(*conditions)
        .order_by(Invoice.created_at.desc(), Invoice.id)
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()
    issues = {}
    if invoices:
        for invoice_id, code in session.execute(
            select(ValidationResult.invoice_id, ValidationResult.rule_code)
            .join(Invoice, Invoice.id == ValidationResult.invoice_id)
            .where(
                Invoice.id.in_([row.id for row in invoices]),
                ValidationResult.run_id == Invoice.validation_run_id,
                ValidationResult.revision == Invoice.revision,
                ValidationResult.passed.is_(False),
            )
            .order_by(ValidationResult.rule_code)
        ):
            issues.setdefault(invoice_id, []).append(code)
    return InvoicePage(
        items=[
            InvoiceSummary.model_validate(row).model_copy(
                update={"issue_codes": issues.get(row.id, [])}
            )
            for row in invoices
        ],
        page=page,
        limit=limit,
        total=total,
    )


@router.get("/invoices/{invoice_id}", response_model=InvoiceDetail)
def detail(invoice_id: uuid.UUID, session: Db):
    invoice = get_invoice(session, invoice_id)
    rules = session.scalars(
        select(ValidationResult)
        .where(
            ValidationResult.invoice_id == invoice.id,
            ValidationResult.revision == invoice.revision,
            ValidationResult.run_id == invoice.validation_run_id,
        )
        .order_by(ValidationResult.created_at, ValidationResult.id)
    ).all()
    return InvoiceDetail(
        **InvoiceSummary.model_validate(invoice).model_dump(),
        extracted_data=invoice.extracted_data,
        reviews=[
            {
                "id": str(review.id),
                "revision": review.revision,
                "reviewer": review.reviewer,
                "decision": review.decision.value,
                "notes": review.notes,
                "payload_sha256": review.payload_sha256,
                "created_at": review.created_at,
            }
            for review in session.scalars(
                select(InvoiceReview)
                .where(InvoiceReview.invoice_id == invoice.id)
                .order_by(InvoiceReview.created_at, InvoiceReview.id)
            ).all()
        ],
        ledger_entry_id=session.scalar(
            select(LedgerEntry.id).where(LedgerEntry.invoice_id == invoice.id)
        ),
        processing_attempts=[
            {
                "id": str(attempt.id),
                "ordinal": attempt.ordinal,
                "status": attempt.status.value,
                "created_at": attempt.created_at,
                "finished_at": attempt.finished_at,
                "error_code": attempt.error_code,
            }
            for attempt in session.scalars(
                select(ProcessingAttempt)
                .where(ProcessingAttempt.invoice_id == invoice.id)
                .order_by(ProcessingAttempt.ordinal)
            ).all()
        ],
        validations=[
            {
                "rule_code": row.rule_code,
                "severity": row.severity.value,
                "passed": row.passed,
                "message": row.message,
                "expected": row.expected,
                "observed": row.observed,
            }
            for row in rules
        ],
    )


@router.post("/invoices/{invoice_id}/process", response_model=ProcessingResult)
def process(
    invoice_id: uuid.UUID,
    request: Request,
    session: Db,
    actor: Operator,
    extractor: Annotated[Extractor, Depends(get_extractor)],
    retry: bool = False,
):
    invoice, attempt = process_invoice(
        session,
        invoice_id,
        request.app.state.settings,
        extractor,
        actor,
        retry,
    )
    return ProcessingResult(
        invoice_id=invoice.id,
        status=invoice.status,
        revision=invoice.revision,
        attempt_id=attempt.id if attempt else None,
        error_code=attempt.error_code if attempt else None,
    )


@router.get("/invoices/{invoice_id}/file")
def original(invoice_id: uuid.UUID, request: Request, session: Db):
    invoice = get_invoice(session, invoice_id)
    path = resolve_private_file(request.app.state.settings.storage_dir, invoice.file_path)
    return FileResponse(
        path,
        media_type=invoice.mime_type,
        filename=invoice.filename,
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.get("/invoices/{invoice_id}/audit", response_model=list[AuditSummary])
def audit(invoice_id: uuid.UUID, session: Db):
    get_invoice(session, invoice_id)
    return session.scalars(
        select(AuditEvent)
        .where(AuditEvent.invoice_id == invoice_id)
        .order_by(AuditEvent.created_at, AuditEvent.id)
    ).all()


@router.get("/vendors", response_model=list[VendorSummary])
def vendors(session: Db):
    return session.scalars(select(Vendor).order_by(Vendor.display_name)).all()


@router.patch("/invoices/{invoice_id}", response_model=InvoiceActionResult)
def correct(invoice_id: uuid.UUID, body: CorrectionRequest, session: Db, actor: Operator):
    return action_result(correct_invoice(session, invoice_id, body, actor))


@router.post("/invoices/{invoice_id}/revalidate", response_model=InvoiceActionResult)
def revalidate(
    invoice_id: uuid.UUID, body: RevisionRequest, request: Request, session: Db, actor: Operator
):
    return action_result(
        revalidate_invoice(session, invoice_id, body, request.app.state.settings, actor)
    )


@router.post("/invoices/{invoice_id}/review", response_model=InvoiceActionResult)
def review(
    invoice_id: uuid.UUID, body: ReviewRequest, request: Request, session: Db, actor: Operator
):
    invoice, recorded = review_invoice(session, invoice_id, body, request.app.state.settings, actor)
    return action_result(invoice, recorded)


@router.post("/invoices/{invoice_id}/post", response_model=LedgerSummary)
def post(
    invoice_id: uuid.UUID, body: RevisionRequest, request: Request, session: Db, actor: Operator
):
    return ledger_summary(
        post_invoice(session, invoice_id, body, request.app.state.settings, actor)
    )


@router.post("/vendors", response_model=VendorSummary, status_code=201)
def add_vendor(body: VendorCreate, session: Db, actor: Operator):
    return create_vendor(session, body, actor)


def posted_ledger_query():
    return (
        select(LedgerEntry, Vendor.display_name)
        .join(Invoice, Invoice.id == LedgerEntry.invoice_id)
        .join(Vendor, Vendor.id == LedgerEntry.vendor_id)
        .where(Invoice.status == InvoiceStatus.POSTED)
    )


@router.get("/ledger", response_model=LedgerPage)
def ledger(
    session: Db, page: int = Query(default=1, ge=1), limit: int = Query(default=25, ge=1, le=100)
):
    query = posted_ledger_query()
    total = session.scalar(select(func.count()).select_from(query.subquery()))
    rows = session.execute(
        query.order_by(LedgerEntry.posted_at.desc(), LedgerEntry.id)
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()
    return LedgerPage(
        items=[ledger_summary(entry, name) for entry, name in rows],
        page=page,
        limit=limit,
        total=total,
    )


@router.get("/ledger/export.csv")
def download_ledger(session: Db):
    rows = session.execute(
        posted_ledger_query().order_by(LedgerEntry.posted_at, LedgerEntry.id)
    ).all()
    filename = f"invoice-ledger-{datetime.now(UTC):%Y%m%d}.csv"
    return Response(
        export_csv(rows),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/stats")
def stats(session: Db):
    counts = {status.value: 0 for status in InvoiceStatus}
    for status, count in session.execute(
        select(Invoice.status, func.count()).group_by(Invoice.status)
    ):
        counts[status.value] = count
    posted = {
        currency: str(total)
        for currency, total in session.execute(
            select(LedgerEntry.currency, func.sum(LedgerEntry.total))
            .join(Invoice, Invoice.id == LedgerEntry.invoice_id)
            .where(Invoice.status == InvoiceStatus.POSTED)
            .group_by(LedgerEntry.currency)
        )
    }
    flagged = {}
    for (payload,) in session.execute(
        select(Invoice.current_data).where(Invoice.status == InvoiceStatus.NEEDS_REVIEW)
    ):
        if payload and payload.get("currency") and payload.get("total") is not None:
            currency = payload["currency"].strip().upper()
            flagged[currency] = flagged.get(currency, Decimal(0)) + Decimal(payload["total"])
    return {
        "total_invoices": sum(counts.values()),
        "by_status": counts,
        "posted_totals_by_currency": posted,
        "flagged_totals_by_currency": {code: str(total) for code, total in flagged.items()},
        "duplicate_invoices": session.scalar(
            select(func.count(Invoice.id)).where(
                select(ValidationResult.id)
                .where(
                    ValidationResult.invoice_id == Invoice.id,
                    ValidationResult.run_id == Invoice.validation_run_id,
                    ValidationResult.revision == Invoice.revision,
                    ValidationResult.rule_code == "DUPLICATE_INVOICE",
                    ValidationResult.passed.is_(False),
                    ValidationResult.severity == Severity.BLOCKER,
                )
                .exists()
            )
        ),
        "recent_activity": [
            {
                "id": str(event.id),
                "invoice_id": str(event.invoice_id) if event.invoice_id else None,
                "event_type": event.event_type,
                "actor": event.actor,
                "created_at": event.created_at.isoformat(),
            }
            for event in session.scalars(
                select(AuditEvent).order_by(AuditEvent.created_at.desc(), AuditEvent.id).limit(8)
            )
        ],
    }
