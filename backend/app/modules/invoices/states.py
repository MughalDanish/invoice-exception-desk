from app.core.errors import AppError
from app.db.models import InvoiceStatus
from app.modules.audit.service import record_event

TRANSITIONS = {
    InvoiceStatus.RECEIVED: {InvoiceStatus.EXTRACTING},
    InvoiceStatus.EXTRACTING: {
        InvoiceStatus.READY_TO_POST,
        InvoiceStatus.NEEDS_REVIEW,
        InvoiceStatus.EXTRACTION_FAILED,
    },
    InvoiceStatus.EXTRACTION_FAILED: {InvoiceStatus.EXTRACTING},
    InvoiceStatus.NEEDS_REVIEW: {
        InvoiceStatus.NEEDS_REVIEW,
        InvoiceStatus.READY_TO_POST,
        InvoiceStatus.REJECTED,
    },
    InvoiceStatus.READY_TO_POST: {InvoiceStatus.NEEDS_REVIEW, InvoiceStatus.POSTED},
    InvoiceStatus.POSTED: set(),
    InvoiceStatus.REJECTED: set(),
}


def transition(session, invoice, target: InvoiceStatus, actor: str, details=None):
    previous = invoice.status
    if target not in TRANSITIONS[previous]:
        raise AppError(409, "INVALID_STATE_TRANSITION", "Invoice cannot enter the requested state")
    invoice.status = target
    record_event(
        session,
        actor,
        "STATE_CHANGED",
        invoice.id,
        {"from": previous.value, "to": target.value, **(details or {})},
    )
