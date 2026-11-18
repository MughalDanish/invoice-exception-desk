"""PostgreSQL queue/checkpoint worker in the same modular monolith. No financial writes."""

import argparse
import json
import logging
import threading
import time
import uuid
from datetime import timedelta

from langsmith import tracing_context
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.db.models import InvestigationRun, InvestigationToolResult, Invoice
from app.modules.investigation.checkpoints import checkpoint_connection, setup_checkpoints
from app.modules.investigation.graph import build_graph
from app.modules.investigation.providers import MockInvestigationProvider
from app.modules.investigation.queue import (
    MAX_ATTEMPTS,
    claim_next,
    database_now,
    event,
    heartbeat,
    owned,
)
from app.modules.investigation.schemas import InvestigationReport, InvoiceSnapshot
from app.modules.investigation.service import locked_invoice, matches


class LostLease(Exception):
    pass


class TransientInvestigationError(Exception):
    """Explicit bounded retry signal; malformed model output is never automatically retried."""


def locked_run(session, run_id):
    return session.scalar(
        select(InvestigationRun)
        .where(InvestigationRun.id == run_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def require_claim(session, claim):
    run = locked_run(session, claim.run_id)
    if not owned(run, claim, database_now(session)):
        raise LostLease()
    return run


def finish(factory, claim, report=None, error=None, transient=False):
    """Lock invoice then run, matching enqueue/control lock order; fence every publication."""
    with factory.begin() as session:
        initial = session.get(InvestigationRun, claim.run_id)
        invoice = locked_invoice(session, initial.invoice_id)
        run = require_claim(session, claim)
        now = database_now(session)
        if not matches(invoice, run, session):
            run.status = "STALE"
        elif error and transient and run.attempts < MAX_ATTEMPTS:
            run.status = "QUEUED"
            run.available_at = now + timedelta(seconds=min(8, 2 ** (run.attempts - 1)))
            run.error_code = "INVESTIGATION_RETRY_SCHEDULED"
        elif error:
            run.status = "FAILED"
            run.error_code = "INVESTIGATION_FAILED"
        else:
            run.status = "COMPLETED"
            run.report = InvestigationReport.model_validate(report).model_dump(mode="json")
            run.error_code = None
        run.finished_at = None if run.status == "QUEUED" else now
        run.lease_owner = run.lease_until = None
        event(session, run, run.status, attempt=run.attempts)


def save_step(factory, claim, values, next_nodes):
    with factory.begin() as session:
        run = require_claim(session, claim)
        # Cache only immutable tool outputs; same key with different content is corruption.
        for name, result in values.get("tool_results", {}).items():
            payload = result.model_dump(mode="json")
            existing = session.scalar(
                select(InvestigationToolResult).where(
                    InvestigationToolResult.run_id == run.id,
                    InvestigationToolResult.tool_name == name,
                )
            )
            if existing and existing.result != payload:
                raise ValueError("Conflicting persisted tool result")
            if existing is None:
                session.add(InvestigationToolResult(run_id=run.id, tool_name=name, result=payload))
        event(
            session,
            run,
            "CHECKPOINTED",
            next_nodes=list(next_nodes),
            tools=len(values.get("tool_results", {})),
        )


def execute_claim(factory, claim, *, lease_seconds=30, provider=None, after_step=None):
    """One dedicated DB connection holds the session lock AND performs checkpoint writes.

    Lease expiry can fence this worker, but another worker cannot touch checkpoints
    until this session lock is released. Losing this connection also stops its saver.
    """
    engine = factory.kw["bind"]
    stop = threading.Event()
    lost = threading.Event()

    def renew():
        while not stop.wait(max(0.2, lease_seconds / 3)):
            try:
                if not heartbeat(factory, claim, lease_seconds):
                    lost.set()
                    return
            except Exception:
                lost.set()
                return

    thread = None
    acquired = False
    try:
        with checkpoint_connection(engine) as (connection, saver):
            key = f"ied-investigation:{claim.run_id}"
            acquired = connection.execute(
                "SELECT pg_try_advisory_lock(hashtextextended(%s, 0)) AS acquired", (key,)
            ).fetchone()["acquired"]
            if not acquired:
                # Requeue only OUR claim. The old worker is fenced but may still be
                # shutting down; never race it on a checkpoint stream.
                with factory.begin() as session:
                    run = require_claim(session, claim)
                    run.status = "QUEUED"
                    run.available_at = database_now(session) + timedelta(seconds=1)
                    run.attempts -= 1  # No execution happened; lock contention is not an attempt.
                    run.lease_owner = run.lease_until = None
                    event(session, run, "LOCK_BUSY")
                return False
            try:
                with factory.begin() as session:
                    run = require_claim(session, claim)
                    invoice = session.get(Invoice, run.invoice_id)
                    if not matches(invoice, run, session):
                        run.status, run.finished_at = "STALE", database_now(session)
                        run.lease_owner = run.lease_until = None
                        event(session, run, "STALE")
                        return True
                    snapshot = InvoiceSnapshot.model_validate_json(json.dumps(run.snapshot))
                graph = build_graph(provider or MockInvestigationProvider(), checkpointer=saver)
                config = {
                    "configurable": {"thread_id": str(claim.run_id)},
                    "recursion_limit": 16,
                    "max_concurrency": 3,
                    "callbacks": [],
                }
                thread = threading.Thread(target=renew, daemon=True)
                thread.start()
                started = time.monotonic()
                state = graph.get_state(config)
                initial = (
                    {"run_id": claim.run_id, "snapshot": snapshot, "findings": {}}
                    if not state.values
                    else None
                )
                with tracing_context(enabled=False):
                    for _ in range(24):
                        if lost.is_set() or time.monotonic() - started > 90:
                            raise LostLease() if lost.is_set() else TimeoutError()
                        with factory.begin() as session:
                            require_claim(session, claim)
                        if initial is not None or state.next:
                            graph.invoke(
                                initial, config=config, interrupt_after="*", durability="sync"
                            )
                            initial = None
                            state = graph.get_state(config)
                            save_step(factory, claim, state.values, state.next)
                            if after_step:
                                after_step(claim, state)
                        if not state.next:
                            report = InvestigationReport.model_validate(state.values["report"])
                            finish(factory, claim, report=report)
                            return True
                    raise ValueError("Checkpoint step budget exceeded")
            finally:
                connection.execute("SELECT pg_advisory_unlock(hashtextextended(%s, 0))", (key,))
    except LostLease:
        return False
    except Exception as exc:
        logging.getLogger(__name__).warning(
            "Investigation worker failed run=%s error_type=%s", claim.run_id, type(exc).__name__
        )
        try:
            finish(
                factory,
                claim,
                error=True,
                transient=isinstance(
                    exc,
                    (TransientInvestigationError, TimeoutError, ConnectionError, OperationalError),
                ),
            )
        except LostLease:
            pass
        return False
    finally:
        stop.set()
        if thread:
            thread.join(timeout=2)


def run_once(
    factory,
    *,
    run_id=None,
    owner=None,
    setup=True,
    lease_seconds=30,
    provider=None,
    after_step=None,
):
    if setup:
        setup_checkpoints(factory.kw["bind"])
    claim = claim_next(
        factory, owner or uuid.uuid4().hex, lease_seconds=lease_seconds, run_id=run_id
    )
    return (
        execute_claim(
            factory, claim, lease_seconds=lease_seconds, provider=provider, after_step=after_step
        )
        if claim
        else False
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--setup-only", action="store_true")
    args = parser.parse_args()
    from app.core.config import Settings
    from app.db.session import build_engine, build_session_factory

    settings = Settings()
    if settings.public_demo:
        raise SystemExit("Worker is disabled in public mode")
    engine = build_engine(settings.database_url)
    factory = build_session_factory(engine)
    try:
        setup_checkpoints(engine)
        if args.setup_only:
            return
        owner = uuid.uuid4().hex
        while True:
            worked = run_once(factory, owner=owner, setup=False)
            if args.once:
                return
            if not worked:
                time.sleep(1)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
