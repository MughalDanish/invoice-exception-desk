"""PostgreSQL queue/checkpoint worker in the same modular monolith. No financial writes."""

import argparse
import json
import logging
import threading
import time
import traceback
import uuid
from contextlib import ExitStack
from datetime import datetime, timedelta

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


def finish(
    factory, claim, report=None, error=None, transient=False, error_code=None, error_site=None
):
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
            run.error_code = error_code or "INVESTIGATION_FAILED"
        else:
            if run.mode == "gemini":
                from app.modules.auth.service import active_session
                from app.modules.investigation.budgets import LiveLimitError

                active_session(
                    session,
                    {"sub": str(run.requested_user_id), "sid": str(run.requested_session_id)},
                )
                deadline = (run.budget_metadata or {}).get("deadline")
                if deadline and now >= datetime.fromisoformat(deadline):
                    raise LiveLimitError("INVESTIGATION_DEADLINE")
            run.status = "COMPLETED"
            validated = InvestigationReport.model_validate(report)
            if validated.mode != run.mode:
                raise ValueError("INVESTIGATION_PROVIDER_MODE_MISMATCH")
            run.report = validated.model_dump(mode="json")
            run.error_code = validated.termination_code
            if validated.termination_code:
                run.status = "FAILED"
        run.finished_at = None if run.status == "QUEUED" else now
        run.lease_owner = run.lease_until = None
        details = {"attempt": run.attempts}
        if error_site is not None:
            details["error_site"] = error_site
        event(session, run, run.status, **details)


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


def execute_claim(
    factory,
    claim,
    *,
    lease_seconds=30,
    provider=None,
    after_step=None,
    settings=None,
    mcp_factory=None,
):
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
        with ExitStack() as resources:
            connection, saver = resources.enter_context(checkpoint_connection(engine))
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
                    mode = run.mode
                    model_name = (run.budget_metadata or {}).get("model")
                thread = threading.Thread(target=renew, daemon=True)
                thread.start()
                live_budget = None
                if mode == "gemini":
                    if settings is None or settings.public_demo:
                        raise ValueError("LIVE_WORKER_SETTINGS_REQUIRED")
                    from app.modules.investigation.budgets import LiveBudget
                    from app.modules.investigation.delegation import assert_run_authorized
                    from app.modules.investigation.gemini_provider import (
                        GeminiInvestigationProvider,
                    )
                    from app.modules.investigation.live_graph import build_live_graph
                    from app.modules.investigation.mcp_client import MCPClient

                    def authorize():
                        return assert_run_authorized(settings, factory, claim)

                    authorize()
                    live_budget = LiveBudget(factory, claim, settings)
                    live_budget.remaining()
                    box = resources.enter_context(
                        (mcp_factory or MCPClient)(settings, factory, claim)
                    )
                    live_provider = provider or GeminiInvestigationProvider(
                        api_key=settings.gemini_api_key.get_secret_value(), model=model_name
                    )
                    if provider is None:
                        resources.callback(live_provider.close)
                    graph = build_live_graph(
                        live_provider, box, live_budget, authorize, checkpointer=saver
                    )
                else:
                    graph = build_graph(provider or MockInvestigationProvider(), checkpointer=saver)
                config = {
                    "configurable": {"thread_id": str(claim.run_id)},
                    "recursion_limit": 64 if mode == "gemini" else 16,
                    "max_concurrency": 3,
                    "callbacks": [],
                }
                started = time.monotonic()
                state = graph.get_state(config)
                initial = (
                    {"run_id": claim.run_id, "snapshot": snapshot, "findings": {}}
                    if not state.values
                    else None
                )
                with tracing_context(enabled=False):
                    for _ in range(48 if mode == "gemini" else 24):
                        if live_budget:
                            live_budget.remaining()
                            authorize()
                        if lost.is_set() or (mode != "gemini" and time.monotonic() - started > 90):
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
        frames = traceback.extract_tb(exc.__traceback__)
        last_frame = next(
            (f for f in reversed(frames) if "investigation" in f.filename), frames[-1]
        )
        error_site = f"{last_frame.name}:{last_frame.lineno}"
        logging.getLogger(__name__).warning(
            "Investigation worker failed run=%s error_type=%s error_site=%s",
            claim.run_id,
            type(exc).__name__,
            error_site,
        )
        try:
            from app.core.errors import AppError
            from app.modules.investigation.budgets import LiveLimitError
            from app.modules.investigation.gemini_provider import GeminiInvestigationError

            safe_code = (
                exc.code
                if isinstance(exc, GeminiInvestigationError)
                or isinstance(exc, AppError)
                and exc.code
                in {"INVESTIGATION_DEADLINE", "INVESTIGATION_STALE", "MCP_UNAUTHORIZED"}
                else (str(exc) if isinstance(exc, LiveLimitError) else None)
            )
            finish(
                factory,
                claim,
                error=True,
                transient=isinstance(
                    exc,
                    (TransientInvestigationError, TimeoutError, ConnectionError, OperationalError),
                ),
                error_code=safe_code,
                error_site=error_site,
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
    settings=None,
    mcp_factory=None,
):
    if setup:
        setup_checkpoints(factory.kw["bind"])
    claim = claim_next(
        factory, owner or uuid.uuid4().hex, lease_seconds=lease_seconds, run_id=run_id
    )
    return (
        execute_claim(
            factory,
            claim,
            lease_seconds=lease_seconds,
            provider=provider,
            after_step=after_step,
            settings=settings,
            mcp_factory=mcp_factory,
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
            worked = run_once(factory, owner=owner, setup=False, settings=settings)
            if args.once:
                return
            if not worked:
                time.sleep(1)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
