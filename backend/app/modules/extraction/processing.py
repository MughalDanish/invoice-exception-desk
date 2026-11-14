import hashlib
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.errors import AppError
from app.db.models import AttemptStatus, Invoice, InvoiceStatus, ProcessingAttempt, Severity
from app.modules.audit.service import record_event
from app.modules.extraction.adapters import ExtractionError, parse_extraction
from app.modules.invoices.states import transition
from app.modules.invoices.storage import resolve_private_file
from app.modules.validation.service import validate_current

LEASE = timedelta(minutes=2)


def locked_invoice(session, invoice_id):
    invoice = session.scalar(
        select(Invoice)
        .where(Invoice.id == invoice_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if invoice is None:
        raise AppError(404, "INVOICE_NOT_FOUND", "Invoice not found")
    return invoice


def process_invoice(session, invoice_id, settings, extractor, actor, retry=False):
    # A healthy worker must retain ownership through its entire retry budget.
    lease = (
        max(
            LEASE,
            timedelta(seconds=settings.gemini_timeout_seconds * settings.gemini_max_attempts + 30),
        )
        if settings.ai_mode == "gemini"
        else LEASE
    )
    with session.begin():
        invoice = locked_invoice(session, invoice_id)
        previous = session.scalar(
            select(ProcessingAttempt)
            .where(ProcessingAttempt.invoice_id == invoice.id)
            .order_by(ProcessingAttempt.ordinal.desc())
            .limit(1)
        )
        if invoice.status in (InvoiceStatus.POSTED, InvoiceStatus.REJECTED):
            raise AppError(409, "TERMINAL_INVOICE", "Terminal invoices cannot be processed again")
        if invoice.status in (InvoiceStatus.NEEDS_REVIEW, InvoiceStatus.READY_TO_POST):
            return invoice, previous
        if invoice.status == InvoiceStatus.EXTRACTING:
            if not retry or (previous and previous.created_at > datetime.now(UTC) - lease):
                return invoice, previous
            if previous:
                previous.status = AttemptStatus.FAILED
                previous.finished_at = datetime.now(UTC)
                previous.error_code = "PROCESSING_INTERRUPTED"
            transition(
                session,
                invoice,
                InvoiceStatus.EXTRACTION_FAILED,
                actor,
                {"error_code": "PROCESSING_INTERRUPTED"},
            )
        elif invoice.status == InvoiceStatus.EXTRACTION_FAILED and not retry:
            raise AppError(
                409, "EXPLICIT_RETRY_REQUIRED", "Retry failed extraction with retry=true"
            )
        attempt = ProcessingAttempt(
            id=uuid.uuid4(),
            invoice_id=invoice.id,
            ordinal=previous.ordinal + 1 if previous else 1,
            status=AttemptStatus.RUNNING,
        )
        session.add(attempt)
        transition(
            session, invoice, InvoiceStatus.EXTRACTING, actor, {"attempt_id": str(attempt.id)}
        )
        file_path, mime_type, expected_hash = invoice.file_path, invoice.mime_type, invoice.sha256
        attempt_id = attempt.id

    # No transaction/row lock is held during external model I/O. EXTRACTING is visible.
    data, error_code = None, None
    try:
        path = resolve_private_file(settings.storage_dir, file_path)
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
            raise ExtractionError("SOURCE_FILE_CHANGED")
        data = parse_extraction(extractor.extract(path, mime_type))
    except ExtractionError as exc:
        error_code = exc.code
    except (OSError, AppError):
        error_code = "SOURCE_FILE_UNAVAILABLE"
    except Exception:
        # Never persist or log arbitrary upstream output or exception messages.
        error_code = "EXTRACTION_INTERNAL_ERROR"

    with session.begin():
        invoice = locked_invoice(session, invoice_id)
        attempt = session.get(ProcessingAttempt, attempt_id, populate_existing=True)
        if invoice.status != InvoiceStatus.EXTRACTING or attempt.status != AttemptStatus.RUNNING:
            raise AppError(
                409, "STALE_PROCESSING_ATTEMPT", "A newer processing attempt owns this invoice"
            )
        if error_code is None:
            try:
                rules = validate_current(session, invoice, data, settings.money_tolerance)
            except ExtractionError as exc:
                error_code = exc.code
        attempt.finished_at = datetime.now(UTC)
        if error_code:
            attempt.status = AttemptStatus.FAILED
            attempt.error_code = error_code
            transition(
                session,
                invoice,
                InvoiceStatus.EXTRACTION_FAILED,
                actor,
                {"attempt_id": str(attempt.id), "error_code": error_code},
            )
        else:
            invoice.extracted_data = data.model_dump(mode="json")
            invoice.current_data = data.model_dump(mode="json")
            blockers = [r.code for r in rules if not r.passed and r.severity == Severity.BLOCKER]
            invoice.review_required = invoice.review_required or bool(blockers)
            attempt.status = AttemptStatus.SUCCEEDED
            record_event(
                session,
                actor,
                "VALIDATION_COMPLETED",
                invoice.id,
                {
                    "revision": invoice.revision,
                    "blocker_codes": blockers,
                    "validation_run_id": str(invoice.validation_run_id),
                },
            )
            target = InvoiceStatus.NEEDS_REVIEW if blockers else InvoiceStatus.READY_TO_POST
            transition(session, invoice, target, actor, {"attempt_id": str(attempt.id)})
    return invoice, attempt
