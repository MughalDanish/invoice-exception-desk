from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.errors import AppError
from app.db.models import InvoiceStatus, LedgerEntry
from app.modules.approvals.service import (
    approved_current,
    check_revision,
    require_editable,
    set_review_state,
    validate_for_action,
)
from app.modules.audit.service import record_event
from app.modules.extraction.processing import locked_invoice
from app.modules.invoices.states import transition


def post_invoice(session, invoice_id, body, settings, actor):
    failure = None
    try:
        with session.begin():
            invoice = locked_invoice(session, invoice_id)
            check_revision(invoice, body.expected_revision)
            if invoice.status == InvoiceStatus.POSTED:
                return session.scalar(
                    select(LedgerEntry).where(LedgerEntry.invoice_id == invoice.id)
                )
            require_editable(invoice)
            if invoice.validation_run_id is None:
                raise AppError(
                    409, "REVALIDATION_REQUIRED", "Revalidate the current revision before posting"
                )
            data, blockers = validate_for_action(session, invoice, settings, actor)
            if blockers:
                failure = AppError(
                    409, "VALIDATION_BLOCKED", "Blocking rules: " + ", ".join(blockers)
                )
            elif invoice.review_required and not approved_current(session, invoice):
                failure = AppError(
                    409,
                    "APPROVAL_REQUIRED",
                    "Approve the current revalidated payload before posting",
                )
            if failure:
                set_review_state(session, invoice, actor, blockers)
                record_event(
                    session,
                    actor,
                    "POST_BLOCKED",
                    invoice.id,
                    {
                        "revision": invoice.revision,
                        "code": failure.code,
                        "blocker_codes": blockers,
                    },
                )
                entry = None
            else:
                set_review_state(session, invoice, actor, [])
                entry = LedgerEntry(
                    invoice_id=invoice.id,
                    vendor_id=invoice.vendor_id,
                    invoice_number_normalized=invoice.normalized_invoice_number,
                    currency=data.currency.strip().upper(),
                    total=data.total,
                    posted_by=actor,
                    snapshot={"revision": invoice.revision, "data": invoice.current_data},
                )
                session.add(entry)
                session.flush()
                transition(
                    session,
                    invoice,
                    InvoiceStatus.POSTED,
                    actor,
                    {"ledger_entry_id": str(entry.id), "revision": invoice.revision},
                )
                record_event(
                    session,
                    actor,
                    "LEDGER_POSTED",
                    invoice.id,
                    {
                        "ledger_entry_id": str(entry.id),
                        "revision": invoice.revision,
                        "currency": entry.currency,
                        "total": str(entry.total),
                    },
                )
    except IntegrityError as exc:
        constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        if constraint not in ("uq_ledger_entries_invoice_id", "uq_ledger_vendor_number"):
            raise
        # The failed transaction has rolled back completely. Record the DB guard
        # in a new transaction; never leave a half-posted invoice or audit chain.
        with session.begin():
            invoice = locked_invoice(session, invoice_id)
            if invoice.status == InvoiceStatus.POSTED:
                return session.scalar(
                    select(LedgerEntry).where(LedgerEntry.invoice_id == invoice.id)
                )
            invoice.review_required = True
            invoice.validation_run_id = None
            if invoice.status == InvoiceStatus.READY_TO_POST:
                transition(
                    session,
                    invoice,
                    InvoiceStatus.NEEDS_REVIEW,
                    actor,
                    {"reason": "LEDGER_CONFLICT"},
                )
            record_event(
                session,
                actor,
                "POST_BLOCKED",
                invoice.id,
                {"revision": invoice.revision, "code": "LEDGER_CONFLICT"},
            )
        raise AppError(
            409, "LEDGER_CONFLICT", "Database rejected a duplicate ledger identity"
        ) from exc
    if failure:
        raise failure
    return entry
