import hashlib
import uuid
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import IntegrationDelivery, Invoice, InvoiceStatus, Source
from app.modules.audit.service import record_event
from app.modules.invoices.storage import ValidatedFile


def get_invoice(session: Session, invoice_id: uuid.UUID) -> Invoice:
    invoice = session.get(Invoice, invoice_id)
    if invoice is None:
        raise AppError(404, "INVOICE_NOT_FOUND", "Invoice not found")
    return invoice


def ingest_file(
    session: Session,
    file: ValidatedFile,
    storage_dir: Path,
    actor: str,
    source: Source = Source.api,
    delivery_key: str | None = None,
) -> tuple[Invoice, bool]:
    invoice_id = uuid.uuid4()
    destination = None
    try:
        with session.begin():
            key_hash = hashlib.sha256(delivery_key.encode()).hexdigest() if delivery_key else None
            if key_hash:
                # Separate namespace from file locks; consistent receipt-then-file lock order.
                key_lock = hashlib.sha256(("delivery:" + key_hash).encode()).digest()[:8]
                session.execute(
                    select(func.pg_advisory_xact_lock(int.from_bytes(key_lock, "big", signed=True)))
                )
                receipt = session.scalar(
                    select(IntegrationDelivery).where(IntegrationDelivery.key_sha256 == key_hash)
                )
                if receipt:
                    if receipt.file_sha256 != file.sha256:
                        raise AppError(
                            409,
                            "IDEMPOTENCY_CONFLICT",
                            "Delivery key was already used for a different attachment",
                        )
                    return get_invoice(session, receipt.invoice_id), True
            # All requests for identical bytes serialize across processes, not just threads.
            lock_key = int.from_bytes(bytes.fromhex(file.sha256[:16]), "big", signed=True)
            session.execute(select(func.pg_advisory_xact_lock(lock_key)))
            existing = session.scalar(select(Invoice).where(Invoice.sha256 == file.sha256))
            if existing is not None:
                if key_hash:
                    session.add(
                        IntegrationDelivery(
                            key_sha256=key_hash, file_sha256=file.sha256, invoice_id=existing.id
                        )
                    )
                record_event(
                    session,
                    actor,
                    "DUPLICATE_UPLOAD_RETURNED",
                    existing.id,
                    {"sha256": file.sha256},
                )
                return existing, True

            storage_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            relative_path = f"{invoice_id}{Path(file.filename).suffix}"
            destination = storage_dir / relative_path
            with destination.open("xb") as handle:
                destination.chmod(0o600)
                handle.write(file.content)
            invoice = Invoice(
                id=invoice_id,
                source=source,
                source_message_id=key_hash,
                filename=file.filename,
                mime_type=file.mime_type,
                sha256=file.sha256,
                byte_size=len(file.content),
                file_path=relative_path,
                status=InvoiceStatus.RECEIVED,
            )
            session.add(invoice)
            session.flush()
            if key_hash:
                session.add(
                    IntegrationDelivery(
                        key_sha256=key_hash, file_sha256=file.sha256, invoice_id=invoice.id
                    )
                )
            record_event(
                session,
                actor,
                "INVOICE_RECEIVED",
                invoice.id,
                {
                    "status": InvoiceStatus.RECEIVED.value,
                    "sha256": file.sha256,
                    "source": source.value,
                },
            )
        return invoice, False
    except Exception:
        # Remove only this request's file if its DB transaction did not commit.
        if destination is not None:
            destination.unlink(missing_ok=True)
        raise
