"""Operator controls affect advisory job metadata only, never financial state."""

from sqlalchemy import func, select

from app.core.errors import AppError
from app.db.models import InvestigationEvent, InvestigationRun
from app.modules.investigation.queue import MAX_ATTEMPTS, database_now, event
from app.modules.investigation.service import locked_invoice, matches, view


def control(session, run_id, actor, action):
    with session.begin():
        initial = session.get(InvestigationRun, run_id)
        if initial is None:
            raise AppError(404, "INVESTIGATION_NOT_FOUND", "Investigation not found")
        invoice = locked_invoice(session, initial.invoice_id)
        run = session.scalar(
            select(InvestigationRun)
            .where(InvestigationRun.id == run_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if run.requested_by != actor:
            raise AppError(
                403,
                "INVESTIGATION_OWNER_REQUIRED",
                "Only the requesting operator can control this run",
            )
        if run.provider_version != "scripted-durable-v4":
            raise AppError(409, "LEGACY_INVESTIGATION", "Start a new investigation for legacy runs")
        now = database_now(session)
        if action == "cancel":
            if run.status == "CANCELLED":
                return view(run, invoice, session)
            if run.status not in ("QUEUED", "RUNNING"):
                raise AppError(409, "INVESTIGATION_TERMINAL", "Investigation is already terminal")
            run.status, run.cancel_requested, run.finished_at = "CANCELLED", True, now
        else:
            if run.status != "FAILED" or run.attempts >= MAX_ATTEMPTS:
                raise AppError(
                    409,
                    "INVESTIGATION_RETRY_DENIED",
                    "Only a failed run with attempts remaining can retry",
                )
            if not matches(invoice, run, session):
                raise AppError(
                    409, "STALE_INVESTIGATION", "Start a new investigation for current evidence"
                )
            run.status, run.available_at, run.finished_at = "QUEUED", now, None
            run.error_code = None
        run.fence += 1
        run.lease_owner = run.lease_until = None
        event(session, run, "CANCELLED" if action == "cancel" else "RETRY_REQUESTED")
        session.flush()
        return view(run, invoice, session)


def list_runs(session, invoice_id, limit, offset):
    from app.db.models import Invoice

    invoice = session.get(Invoice, invoice_id)
    if invoice is None:
        raise AppError(404, "INVOICE_NOT_FOUND", "Invoice not found")
    where = InvestigationRun.invoice_id == invoice_id
    total = session.scalar(select(func.count()).select_from(InvestigationRun).where(where))
    rows = session.scalars(
        select(InvestigationRun)
        .where(where)
        .order_by(InvestigationRun.created_at.desc(), InvestigationRun.id)
        .offset(offset)
        .limit(limit)
    ).all()
    return {
        "total": total,
        "items": [view(run, invoice, session).model_copy(update={"report": None}) for run in rows],
        "limit": limit,
        "offset": offset,
    }


def events(session, run_id, after_seq, limit):
    if session.get(InvestigationRun, run_id) is None:
        raise AppError(404, "INVESTIGATION_NOT_FOUND", "Investigation not found")
    rows = session.scalars(
        select(InvestigationEvent)
        .where(
            InvestigationEvent.run_id == run_id,
            InvestigationEvent.seq > after_seq,
        )
        .order_by(InvestigationEvent.seq)
        .limit(limit)
    ).all()
    return {
        "items": [
            {
                "seq": row.seq,
                "event_type": row.event_type,
                "created_at": row.created_at,
                "details": row.details,
            }
            for row in rows
        ],
        "next_after_seq": rows[-1].seq if rows else after_seq,
    }
