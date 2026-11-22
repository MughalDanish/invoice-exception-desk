"""Day 12: real PostgreSQL queue, fenced publication and killed-process recovery."""

import json
import os
import subprocess
import sys
import time
import uuid
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, SecretStr
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.db.models import (
    InvestigationEvent,
    InvestigationRun,
    InvestigationToolResult,
    Invoice,
)
from app.modules.investigation.checkpoints import (
    SafeCheckpointSerializer,
    checkpoint_connection,
    setup_checkpoints,
)
from app.modules.investigation.providers import MockInvestigationProvider
from app.modules.investigation.queue import claim_next, database_now, heartbeat
from app.modules.investigation.worker import (
    LostLease,
    TransientInvestigationError,
    execute_claim,
    finish,
    run_once,
    save_step,
)
from tests.conftest import operator_auth
from tests.test_investigation import financial_state, prepared, snapshot
from tests.test_investigation_parallel import evidence


def enqueue(client, identifier, key="durable-test"):
    response = client.post(
        f"/api/v1/invoices/{identifier}/investigations",
        json={"expected_revision": 1, "idempotency_key": key},
        **operator_auth(client),
    )
    assert response.status_code == 202, response.text
    return uuid.UUID(response.json()["run_id"]), response


def read_run(engine, run_id):
    with Session(engine) as session:
        row = session.get(InvestigationRun, run_id)
        return {
            "status": row.status,
            "attempts": row.attempts,
            "fence": row.fence,
            "error": row.error_code,
            "report": row.report,
            "available": row.available_at,
            "lease_until": row.lease_until,
        }


def expire_lease(engine, run_id):
    with Session(engine) as session, session.begin():
        row = session.get(InvestigationRun, run_id)
        row.lease_until = database_now(session) - timedelta(seconds=1)


def make_ready(engine, run_id):
    with Session(engine) as session, session.begin():
        session.get(InvestigationRun, run_id).available_at = database_now(session)


def test_enqueue_is_nonblocking_idempotent_and_worker_preserves_financial_state(
    pg_client, pg_engine, monkeypatch
):
    identifier = prepared(pg_client, pg_engine)
    before = financial_state(pg_engine)
    calls = []
    original = MockInvestigationProvider.plan

    def counted(self, captured):
        calls.append(captured.invoice_id)
        return original(self, captured)

    monkeypatch.setattr(MockInvestigationProvider, "plan", counted)
    run_id, response = enqueue(pg_client, identifier)
    assert response.json()["status"] == "QUEUED"
    assert response.json()["execution"] == "durable_worker"
    assert response.json()["report"] is None and calls == []
    again, _ = enqueue(pg_client, identifier)
    assert again == run_id
    assert run_once(pg_client.app.state.session_factory, run_id=run_id)
    assert calls == [uuid.UUID(identifier)]
    result = pg_client.get(f"/api/v1/investigations/{run_id}", **operator_auth(pg_client))
    assert result.json()["status"] == "COMPLETED" and result.json()["applicable"]
    assert not run_once(pg_client.app.state.session_factory, run_id=run_id)
    assert financial_state(pg_engine) == before
    with Session(pg_engine) as session:
        events = session.scalars(
            select(InvestigationEvent)
            .where(InvestigationEvent.run_id == run_id)
            .order_by(InvestigationEvent.seq)
        ).all()
        assert [event.seq for event in events] == list(range(1, len(events) + 1))
        assert events[0].event_type == "QUEUED" and events[-1].event_type == "COMPLETED"
        assert any(event.event_type == "CHECKPOINTED" for event in events)
        assert all(
            set(event.details) <= {"attempt", "generation", "next_nodes", "tools"}
            for event in events
        )
        cached = session.scalars(
            select(InvestigationToolResult).where(InvestigationToolResult.run_id == run_id)
        ).all()
        assert {row.tool_name for row in cached} == set(result.json()["report"]["tools_used"])
    page = pg_client.get(
        f"/api/v1/investigations/{run_id}/events?limit=2", **operator_auth(pg_client)
    )
    assert len(page.json()["items"]) == 2
    after = page.json()["next_after_seq"]
    next_page = pg_client.get(
        f"/api/v1/investigations/{run_id}/events?after_seq={after}", **operator_auth(pg_client)
    )
    assert next_page.json()["items"][0]["seq"] == after + 1


def test_killed_child_resumes_persisted_checkpoint_without_replanning(
    pg_client, pg_engine, tmp_path
):
    identifier = prepared(pg_client, pg_engine)
    before = financial_state(pg_engine)
    run_id, _ = enqueue(pg_client, identifier)
    with pg_engine.connect() as connection:
        schema = connection.scalar(text("SELECT current_schema()"))
    marker = tmp_path / "checkpoint-ready.json"
    child_code = r"""
import json, os, time, uuid
from pathlib import Path
from sqlalchemy import create_engine
from app.db.session import build_session_factory
from app.modules.investigation.worker import run_once
engine = create_engine(os.environ["IED_TEST_DB_URL"], connect_args={
    "connect_timeout": 5, "options": "-csearch_path=" + os.environ["IED_TEST_DB_SCHEMA"]})
def checkpoint(claim, state):
    if state.values.get("tool_results"):
        Path(os.environ["IED_TEST_MARKER"]).write_text(
            json.dumps({"next": list(state.next)}), encoding="utf-8")
        while True:
            time.sleep(0.1)
run_once(build_session_factory(engine), run_id=uuid.UUID(os.environ["IED_TEST_RUN"]),
         lease_seconds=30, after_step=checkpoint)
"""
    env = os.environ.copy()
    env.update(
        {
            "IED_TEST_DB_URL": pg_engine.url.render_as_string(hide_password=False),
            "IED_TEST_DB_SCHEMA": schema,
            "IED_TEST_MARKER": str(marker),
            "IED_TEST_RUN": str(run_id),
            "LANGSMITH_TRACING": "false",
        }
    )
    child = subprocess.Popen(
        [sys.executable, "-c", child_code],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 45
        while not marker.exists() and child.poll() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        assert marker.exists(), "Child did not reach the persisted supervisor checkpoint"
        assert json.loads(marker.read_text(encoding="utf-8"))["next"]
        child.terminate()
        child.wait(timeout=10)
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=10)
    with Session(pg_engine) as session:
        cached_before = {
            row.tool_name: row.result
            for row in session.scalars(
                select(InvestigationToolResult).where(InvestigationToolResult.run_id == run_id)
            )
        }
    assert cached_before and read_run(pg_engine, run_id)["status"] == "RUNNING"
    expire_lease(pg_engine, run_id)

    class Resuming(MockInvestigationProvider):
        def plan(self, captured):
            pytest.fail("Persisted supervisor checkpoint must not plan or call tools again")

    assert run_once(pg_client.app.state.session_factory, run_id=run_id, provider=Resuming())
    assert read_run(pg_engine, run_id)["status"] == "COMPLETED"
    assert read_run(pg_engine, run_id)["attempts"] == 2
    with Session(pg_engine) as session:
        cached_after = {
            row.tool_name: row.result
            for row in session.scalars(
                select(InvestigationToolResult).where(InvestigationToolResult.run_id == run_id)
            )
        }
    assert cached_before == cached_after
    assert financial_state(pg_engine) == before


def test_lease_fence_rejects_late_publication_checkpoint_and_heartbeat(pg_client, pg_engine):
    identifier = prepared(pg_client, pg_engine)
    run_id, _ = enqueue(pg_client, identifier)
    factory = pg_client.app.state.session_factory
    setup_checkpoints(pg_engine)
    old = claim_next(factory, "old-worker", run_id=run_id)
    expire_lease(pg_engine, run_id)
    current = claim_next(factory, "new-worker", run_id=run_id)
    assert current.fence > old.fence
    with pytest.raises(LostLease):
        finish(factory, old, error=True)
    with pytest.raises(LostLease):
        save_step(factory, old, {}, ())
    assert not heartbeat(factory, old, 30)
    assert execute_claim(factory, current)
    assert read_run(pg_engine, run_id)["status"] == "COMPLETED"


def test_advisory_lock_prevents_competing_resumer_checkpoint_writes(pg_client, pg_engine):
    identifier = prepared(pg_client, pg_engine)
    run_id, _ = enqueue(pg_client, identifier)
    factory = pg_client.app.state.session_factory
    setup_checkpoints(pg_engine)
    old = claim_next(factory, "old-worker", run_id=run_id)
    key = f"ied-investigation:{run_id}"
    with checkpoint_connection(pg_engine) as (connection, _):
        connection.execute("SELECT pg_advisory_lock(hashtextextended(%s, 0))", (key,))
        try:
            expire_lease(pg_engine, run_id)
            competing = claim_next(factory, "resumer", run_id=run_id)
            assert not execute_claim(factory, competing)
            with Session(pg_engine) as session:
                count = session.scalar(
                    text("SELECT count(*) FROM checkpoints WHERE thread_id=:id"),
                    {"id": str(run_id)},
                )
                assert count == 0
                assert (
                    session.scalar(
                        select(func.count())
                        .select_from(InvestigationEvent)
                        .where(
                            InvestigationEvent.run_id == run_id,
                            InvestigationEvent.event_type == "LOCK_BUSY",
                        )
                    )
                    == 1
                )
            assert read_run(pg_engine, run_id)["status"] == "QUEUED"
            with pytest.raises(LostLease):
                save_step(factory, old, {}, ())
        finally:
            connection.execute("SELECT pg_advisory_unlock(hashtextextended(%s, 0))", (key,))
    make_ready(pg_engine, run_id)
    assert run_once(factory, run_id=run_id)


@pytest.mark.parametrize("during_graph", [False, True])
def test_cancellation_fences_queued_and_running_jobs(pg_client, pg_engine, during_graph):
    identifier = prepared(pg_client, pg_engine)
    before = financial_state(pg_engine)
    run_id, _ = enqueue(pg_client, identifier)
    factory = pg_client.app.state.session_factory
    cancelled = []

    def cancel(*_):
        if not cancelled:
            response = pg_client.post(
                f"/api/v1/investigations/{run_id}/cancel", **operator_auth(pg_client)
            )
            assert response.status_code == 200
            assert response.json()["status"] == "CANCELLED"
            cancelled.append(True)

    if during_graph:
        assert not run_once(factory, run_id=run_id, after_step=cancel)
    else:
        cancel()
        assert not run_once(factory, run_id=run_id)
    assert read_run(pg_engine, run_id)["status"] == "CANCELLED"
    assert read_run(pg_engine, run_id)["report"] is None
    assert financial_state(pg_engine) == before


def test_transient_retries_are_bounded_backoff_and_not_immediately_claimable(pg_client, pg_engine):
    identifier = prepared(pg_client, pg_engine)
    run_id, _ = enqueue(pg_client, identifier)
    factory = pg_client.app.state.session_factory

    class TemporaryFailure(MockInvestigationProvider):
        def plan(self, captured):
            raise TransientInvestigationError("synthetic transient failure")

    for attempt in range(1, 4):
        with Session(pg_engine) as session:
            before = database_now(session)
        assert not run_once(factory, run_id=run_id, provider=TemporaryFailure())
        result = read_run(pg_engine, run_id)
        assert result["attempts"] == attempt
        if attempt < 3:
            assert result["status"] == "QUEUED"
            assert result["available"] >= before + timedelta(seconds=2 ** (attempt - 1))
            assert claim_next(factory, "too-soon", run_id=run_id) is None
            make_ready(pg_engine, run_id)
        else:
            assert result["status"] == "FAILED" and result["report"] is None
    assert not run_once(factory, run_id=run_id, provider=TemporaryFailure())


@pytest.mark.parametrize("change", ["invoice", "evidence"])
def test_snapshot_change_before_worker_marks_stale_without_provider_call(
    pg_client, pg_engine, change
):
    identifier = prepared(pg_client, pg_engine)
    run_id, _ = enqueue(pg_client, identifier)
    with Session(pg_engine) as session, session.begin():
        invoice = session.get(Invoice, uuid.UUID(identifier))
        if change == "invoice":
            invoice.current_data = invoice.current_data | {
                "invoice_number": "synthetic-new-revision"
            }
        else:
            session.add(evidence(invoice.id, invoice.normalized_vendor_name))

    class MustNotRun(MockInvestigationProvider):
        def plan(self, captured):
            pytest.fail("Stale snapshot must be rejected before provider invocation")

    assert run_once(pg_client.app.state.session_factory, run_id=run_id, provider=MustNotRun())
    assert read_run(pg_engine, run_id)["status"] == "STALE"
    assert read_run(pg_engine, run_id)["report"] is None


def test_safe_serializer_roundtrips_contracts_and_rejects_pickle_unregistered_types():
    serde = SafeCheckpointSerializer()
    captured = snapshot()
    original = {"snapshot": captured, "id": captured.invoice_id, "tuple": ("a",), "bytes": b"x"}
    assert serde.loads_typed(serde.dumps_typed(original)) == original
    with pytest.raises(ValueError):
        serde.loads_typed(("pickle", b"not executable"))
    with pytest.raises(ValueError):
        serde.loads_typed(("safe-json-v1", b'["model", "evil.module.Class", "{}"]'))

    class Unregistered(BaseModel):
        value: str

    with pytest.raises(ValueError):
        serde.dumps_typed(Unregistered(value="blocked"))
    with pytest.raises(ValueError):
        serde.dumps_typed(float("nan"))
    # A data dictionary with a type-looking key is data, not an import directive.
    marker = {"__type__": "evil.module.Class", "value": "data"}
    assert serde.loads_typed(serde.dumps_typed(marker)) == marker


def test_control_and_history_endpoints_enforce_session_csrf_owner_and_pagination(
    pg_client, pg_engine, settings
):
    identifier = prepared(pg_client, pg_engine)
    before = financial_state(pg_engine)
    run_id, _ = enqueue(pg_client, identifier)
    settings.n8n_integration_key = SecretStr("synthetic-test-integration-key")
    endpoints = [
        ("POST", f"/api/v1/investigations/{run_id}/cancel"),
        ("POST", f"/api/v1/investigations/{run_id}/retry"),
        ("GET", f"/api/v1/investigations/{run_id}/events"),
        ("GET", f"/api/v1/invoices/{identifier}/investigations"),
    ]
    # Integration authentication is intentionally not operator authentication.
    anonymous = TestClient(pg_client.app)
    try:
        for method, path in endpoints:
            assert anonymous.request(method, path).status_code == 401
            assert (
                anonymous.request(
                    method,
                    path,
                    headers={"X-Integration-Key": "synthetic-test-integration-key"},
                ).status_code
                == 401
            )
    finally:
        anonymous.close()
    for action in ("cancel", "retry"):
        response = pg_client.post(
            f"/api/v1/investigations/{run_id}/{action}",
            headers={"X-CSRF-Token": "synthetic-wrong-csrf"},
            **operator_auth(pg_client),
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "CSRF_REJECTED"
    with Session(pg_engine) as session, session.begin():
        session.get(InvestigationRun, run_id).requested_by = "different-synthetic-operator"
    for action in ("cancel", "retry"):
        response = pg_client.post(
            f"/api/v1/investigations/{run_id}/{action}", **operator_auth(pg_client)
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "INVESTIGATION_OWNER_REQUIRED"
    assert read_run(pg_engine, run_id)["status"] == "QUEUED"
    list_path = f"/api/v1/invoices/{identifier}/investigations"
    event_path = f"/api/v1/investigations/{run_id}/events"
    for path, query in [
        (list_path, "limit=0"),
        (list_path, "limit=51"),
        (list_path, "offset=-1"),
        (event_path, "limit=0"),
        (event_path, "limit=101"),
        (event_path, "after_seq=-1"),
    ]:
        assert pg_client.get(f"{path}?{query}", **operator_auth(pg_client)).status_code == 422
    page = pg_client.get(f"{list_path}?limit=1&offset=0", **operator_auth(pg_client))
    assert page.status_code == 200 and page.json()["total"] == 1
    assert len(page.json()["items"]) == 1 and page.json()["items"][0]["report"] is None
    empty = pg_client.get(f"{list_path}?limit=1&offset=1", **operator_auth(pg_client))
    assert empty.json()["items"] == []
    assert financial_state(pg_engine) == before


def test_explicit_retry_resumes_failed_checkpoint_and_rejects_unsafe_states(pg_client, pg_engine):
    identifier = prepared(pg_client, pg_engine)
    before = financial_state(pg_engine)
    factory = pg_client.app.state.session_factory

    class NonTransientFailure(MockInvestigationProvider):
        def plan(self, captured):
            raise RuntimeError("synthetic nontransient failure")

    def failed(key):
        run_id, _ = enqueue(pg_client, identifier, key=key)
        assert not run_once(factory, run_id=run_id, provider=NonTransientFailure())
        result = read_run(pg_engine, run_id)
        assert result["status"] == "FAILED" and result["attempts"] == 1
        return run_id

    run_id = failed("explicit-retry-success")
    with pg_engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT count(*) FROM checkpoints WHERE thread_id=:id"), {"id": str(run_id)}
            )
            > 0
        )
    retried = pg_client.post(f"/api/v1/investigations/{run_id}/retry", **operator_auth(pg_client))
    assert retried.status_code == 200 and retried.json()["status"] == "QUEUED"
    assert run_once(factory, run_id=run_id)
    assert read_run(pg_engine, run_id)["status"] == "COMPLETED"
    assert read_run(pg_engine, run_id)["attempts"] == 2
    terminal = pg_client.post(f"/api/v1/investigations/{run_id}/retry", **operator_auth(pg_client))
    assert terminal.status_code == 409
    assert terminal.json()["error"]["code"] == "INVESTIGATION_RETRY_DENIED"

    stale_id = failed("explicit-retry-stale")
    with Session(pg_engine) as session, session.begin():
        invoice = session.get(Invoice, uuid.UUID(identifier))
        session.add(evidence(invoice.id, invoice.normalized_vendor_name))
    stale = pg_client.post(f"/api/v1/investigations/{stale_id}/retry", **operator_auth(pg_client))
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "STALE_INVESTIGATION"
    assert read_run(pg_engine, stale_id)["status"] == "FAILED"

    exhausted_id = failed("explicit-retry-exhausted")
    with Session(pg_engine) as session, session.begin():
        session.get(InvestigationRun, exhausted_id).attempts = 3
    exhausted = pg_client.post(
        f"/api/v1/investigations/{exhausted_id}/retry", **operator_auth(pg_client)
    )
    assert exhausted.status_code == 409
    assert exhausted.json()["error"]["code"] == "INVESTIGATION_RETRY_DENIED"
    assert financial_state(pg_engine) == before
