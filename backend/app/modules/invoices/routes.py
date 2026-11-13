import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.auth import require_operator
from app.db.models import AuditEvent, Invoice, InvoiceStatus, ValidationResult, Vendor
from app.db.session import get_session
from app.modules.invoices.schemas import (
    AuditSummary,
    InvoiceDetail,
    InvoicePage,
    InvoiceSummary,
    UploadResult,
    VendorSummary,
)
from app.modules.invoices.service import get_invoice, ingest_file
from app.modules.invoices.storage import resolve_private_file, validate_file

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
):
    conditions = []
    if status is not None:
        conditions.append(Invoice.status == status)
    if search:
        # Search characters such as % and _ are literal, not SQL wildcards.
        conditions.append(Invoice.filename.icontains(search, autoescape=True))
    total = session.scalar(select(func.count()).select_from(Invoice).where(*conditions))
    invoices = session.scalars(
        select(Invoice)
        .where(*conditions)
        .order_by(Invoice.created_at.desc(), Invoice.id)
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()
    return InvoicePage(
        items=[InvoiceSummary.model_validate(row) for row in invoices],
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
        )
        .order_by(ValidationResult.created_at, ValidationResult.id)
    ).all()
    return InvoiceDetail(
        **InvoiceSummary.model_validate(invoice).model_dump(),
        extracted_data=invoice.extracted_data,
        current_data=invoice.current_data,
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
