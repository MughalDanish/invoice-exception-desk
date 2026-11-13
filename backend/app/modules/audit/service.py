import uuid

from sqlalchemy.orm import Session

from app.db.models import AuditEvent


def record_event(
    session: Session,
    actor: str,
    event_type: str,
    invoice_id: uuid.UUID | None = None,
    details: dict | None = None,
) -> None:
    session.add(
        AuditEvent(actor=actor, event_type=event_type, invoice_id=invoice_id, details=details or {})
    )
