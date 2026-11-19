"""Killed live-host recovery using fake Gemini, real MCP, and real PostgreSQL."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import InvestigationEvent, InvestigationRun, InvestigationToolResult
from app.modules.investigation.live_schemas import ModelToolCall, ProtocolContent, ProtocolPart
from app.modules.investigation.worker import run_once
from tests.test_investigation import financial_state, prepared
from tests.test_investigation_durable import enqueue, expire_lease
from tests.test_investigation_live import FakeGemini, configure


class HistoryGemini(FakeGemini):
    """A new instance continues solely from durable protocol history, not counters."""

    def step(self, history, definitions, *, timeout_seconds, max_output_tokens):
        returned = {
            p.function_response["name"]
            for content in history
            for p in content.parts
            if p.function_response
        }
        mandatory = json.loads(history[0].parts[0].text)["mandatory_tools"]
        names = (
            ["get_rule_results"]
            if not returned
            else [name for name in mandatory if name not in returned]
        )
        calls = tuple(ModelToolCall(id=None, name=name, args={}) for name in names)
        return self._turn(
            content=ProtocolContent(
                role="model",
                parts=(
                    tuple(ProtocolPart(function_call=call) for call in calls)
                    or (ProtocolPart(text="Evidence gathered; prepare the advisory report."),)
                ),
            ),
            calls=calls,
        )


def test_killed_live_worker_resumes_history_authorization_and_cumulative_budget(
    pg_client, pg_engine, settings, tmp_path
):
    configure(settings, pg_engine)
    identifier = prepared(pg_client, pg_engine)
    before = financial_state(pg_engine)
    run_id, _ = enqueue(pg_client, identifier, "live-kill-resume")
    marker = tmp_path / "live-checkpoint-ready.json"
    code = r"""
import json, os, time, uuid
from pathlib import Path
from app.core.config import Settings
from app.db.session import build_engine, build_session_factory
from app.modules.investigation.worker import run_once
from tests.test_investigation_live_recovery import HistoryGemini
settings = Settings(_env_file=None, **json.loads(os.environ["IED_TEST_SETTINGS"]))
engine = build_engine(settings.database_url)
def checkpoint(claim, state):
    if state.values.get("tool_results") and "model" in state.next:
        Path(os.environ["IED_TEST_MARKER"]).write_text(json.dumps({"next": list(state.next)}))
        while True:
            time.sleep(0.1)
run_once(build_session_factory(engine), run_id=uuid.UUID(os.environ["IED_TEST_RUN"]),
         settings=settings, provider=HistoryGemini(), lease_seconds=30, after_step=checkpoint)
"""
    env = os.environ.copy()
    # Only synthetic fixture credentials are serialized here; no browser JWT or
    # production key. The MCP grandchild still uses its sanitized environment.
    serialized = settings.model_dump(mode="json")
    serialized["auth_jwt_secret"] = settings.auth_jwt_secret.get_secret_value()
    serialized["auth_bootstrap_password"] = "test-password-only"
    serialized["gemini_api_key"] = "synthetic-only-not-a-real-provider-key"
    env.update(
        {
            "IED_TEST_SETTINGS": json.dumps(serialized),
            "IED_TEST_RUN": str(run_id),
            "IED_TEST_MARKER": str(marker),
            "LANGSMITH_TRACING": "false",
        }
    )
    child = subprocess.Popen(
        [sys.executable, "-c", code],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 60
        while not marker.exists() and child.poll() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        assert marker.exists(), "Live child did not reach its persisted tool checkpoint"
        assert json.loads(marker.read_text())["next"] == ["model"]
        with Session(pg_engine) as session:
            row = session.get(InvestigationRun, run_id)
            frozen = json.loads(json.dumps(row.snapshot))
            binding = (row.requested_user_id, row.requested_session_id)
            budget_before = json.loads(json.dumps(row.budget_metadata))
            cached_before = {
                r.tool_name: r.result
                for r in session.scalars(
                    select(InvestigationToolResult).where(InvestigationToolResult.run_id == run_id)
                )
            }
        assert cached_before.keys() == {"get_rule_results"}
        assert budget_before["calls"] and budget_before["calls"][0]["status"] == "COMPLETED"
        child.terminate()
        child.wait(timeout=10)
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=10)
    expire_lease(pg_engine, run_id)
    assert run_once(
        pg_client.app.state.session_factory,
        run_id=run_id,
        settings=settings,
        provider=HistoryGemini(),
    )
    assert not run_once(
        pg_client.app.state.session_factory,
        run_id=run_id,
        settings=settings,
        provider=HistoryGemini(),
    )
    with Session(pg_engine) as session:
        row = session.get(InvestigationRun, run_id)
        assert row.status == "COMPLETED" and row.attempts == 2
        assert row.snapshot == frozen
        assert (row.requested_user_id, row.requested_session_id) == binding
        assert row.budget_metadata["deadline"] == budget_before["deadline"]
        assert row.budget_metadata["calls"][: len(budget_before["calls"])] == budget_before["calls"]
        assert row.budget_metadata["tool_calls"] > budget_before["tool_calls"]
        cached_after = {
            r.tool_name: r.result
            for r in session.scalars(
                select(InvestigationToolResult).where(InvestigationToolResult.run_id == run_id)
            )
        }
        assert all(cached_after[name] == value for name, value in cached_before.items())
        events = session.scalars(
            select(InvestigationEvent).where(InvestigationEvent.run_id == run_id)
        ).all()
        assert sum(e.event_type == "COMPLETED" for e in events) == 1
        assert (
            sum(
                e.event_type == "TOOL_COMPLETED" and e.details["tool"] == "get_rule_results"
                for e in events
            )
            == 1
        )
    assert financial_state(pg_engine) == before
