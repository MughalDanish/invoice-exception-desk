"""Bounded exact evidence capture before fan-out; no shared database sessions."""

from sqlalchemy import select

from app.db.models import InvestigationDocument
from app.modules.investigation.schemas import DocumentEvidence, DocumentSnapshot


def capture_documents(session, invoice) -> DocumentSnapshot:
    supplier = invoice.normalized_vendor_name or ""
    if not supplier:
        return DocumentSnapshot()
    # PostgreSQL DISTINCT ON selects one latest version per source within BOTH scopes.
    rows = session.scalars(
        select(InvestigationDocument)
        .where(
            InvestigationDocument.invoice_id == invoice.id,
            InvestigationDocument.supplier_key == supplier,
        )
        .distinct(InvestigationDocument.source_id)
        .order_by(InvestigationDocument.source_id, InvestigationDocument.version.desc())
        .limit(13)
        .execution_options(populate_existing=True)
    ).all()
    return DocumentSnapshot(
        items=tuple(
            DocumentEvidence(
                source_id=r.source_id,
                version=r.version,
                invoice_id=r.invoice_id,
                supplier_key=r.supplier_key,
                kind=r.kind,
                content_sha256=r.content_sha256,
                text=r.content,
            )
            for r in rows[:12]
        ),
        truncated=len(rows) > 12,
    )
