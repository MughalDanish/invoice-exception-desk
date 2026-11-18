"""Authenticated historical source resolution; no source modification endpoint."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Response
from sqlalchemy import select

from app.core.auth import require_operator
from app.core.errors import AppError
from app.db.models import InvestigationDocument
from app.modules.evidence.schemas import Citation
from app.modules.evidence.search import citation_from_row
from app.modules.invoices.routes import Db
from app.modules.invoices.service import get_invoice

router = APIRouter(prefix="/api/v1", tags=["Evidence"], dependencies=[Depends(require_operator)])


@router.get(
    "/invoices/{invoice_id}/evidence/{source_id}/versions/{version}", response_model=Citation
)
def source(
    invoice_id: UUID,
    source_id: UUID,
    version: Annotated[int, Path(ge=1)],
    session: Db,
    response: Response,
):
    invoice = get_invoice(session, invoice_id)
    row = session.scalar(
        select(InvestigationDocument).where(
            InvestigationDocument.invoice_id == invoice.id,
            InvestigationDocument.supplier_key == (invoice.normalized_vendor_name or ""),
            InvestigationDocument.source_id == source_id,
            InvestigationDocument.version == version,
        )
    )
    if row is None:
        raise AppError(404, "EVIDENCE_NOT_FOUND", "Evidence source not found")
    response.headers["Cache-Control"] = "no-store"
    return citation_from_row(row)
