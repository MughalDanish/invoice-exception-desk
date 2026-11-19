"""Real PostgreSQL/stdio MCP with fake Gemini: no paid calls or model shortcuts."""

import json
from datetime import timedelta

import pytest
from pydantic import SecretStr, ValidationError
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import InvestigationEvent, InvestigationRun
from app.modules.investigation.budgets import LiveBudget, LiveLimitError
from app.modules.investigation.live_schemas import (
    LiveAssertion,
    LiveCritic,
    LiveDraft,
    LiveFinding,
    ModelToolCall,
    ModelTurn,
    ProtocolContent,
    ProtocolPart,
    TokenUsage,
)
from app.modules.investigation.queue import claim_next, database_now
from app.modules.investigation.worker import run_once
from tests.conftest import operator_auth
from tests.test_investigation import financial_state, prepared
from tests.test_investigation_durable import enqueue


def configure(settings, engine):
    with engine.connect() as connection:
        schema = connection.scalar(text("SELECT current_schema()"))
    settings.investigation_mode = "gemini"
    settings.gemini_api_key = SecretStr("synthetic-only-not-a-real-provider-key")
    settings.gemini_model = "synthetic-model-no-network"
    settings.database_url = engine.url.update_query_dict(
        {
            "options": f"-csearch_path={schema}",
        }
    ).render_as_string(hide_password=False)
    return settings


class FakeGemini:
    """Depends on returned MCP evidence, never on a Session or invoice snapshot."""

    model = "synthetic-model-no-network"

    def __init__(self, on_first=None, *, invalid=False, unsafe_args=False, unsafe_tool=False):
        self.turn = 0
        self.on_first = on_first
        self.invalid = invalid
        self.unsafe_args = unsafe_args
        self.unsafe_tool = unsafe_tool

    def estimate_input_tokens(self, payload, timeout_seconds):
        # Test accounting is synthetic; no claim that this estimates live tokens.
        return 200

    @staticmethod
    def _turn(**kwargs):
        return ModelTurn(
            usage=TokenUsage(input_tokens=50, output_tokens=20, thinking_tokens=0, total_tokens=70),
            finish_reason="STOP",
            latency_ms=1,
            **kwargs,
        )

    def step(self, history, definitions, *, timeout_seconds, max_output_tokens):
        self.turn += 1
        if self.turn == 1:
            assert "2300.0000" not in history[0].model_dump_json()
            assert "2500.0000" not in history[0].model_dump_json()
            requested = (
                ModelToolCall(
                    id="first",
                    name="post_to_ledger" if self.unsafe_tool else "get_rule_results",
                    args={"invoice_id": "forbidden"} if self.unsafe_args else {},
                ),
            )
            if self.on_first:
                self.on_first()
        elif self.turn == 2:
            objectives = json.loads(history[0].parts[0].text)["mandatory_tools"]
            requested = tuple(
                ModelToolCall(id=f"followup-{index}", name=name, args={})
                for index, name in enumerate(objectives)
                if name != "get_rule_results"
            )
        else:
            requested = ()
        parts = tuple(ProtocolPart(function_call=call) for call in requested) or (
            ProtocolPart(text="Evidence gathered; prepare an advisory report."),
        )
        return self._turn(content=ProtocolContent(role="model", parts=parts), calls=requested)

    def draft(self, history, *, timeout_seconds, max_output_tokens):
        returned = [
            part.function_response["response"]
            for content in history
            for part in content.parts
            if part.function_response
        ]
        rules = next(result for result in returned if result["name"] == "get_rule_results")
        rule = rules["data"]["rules"][0]
        identifier = "invented-reference" if self.invalid else rules["evidence_id"]
        candidate = LiveDraft(
            summary="Recorded discrepancy requires original evidence review.",
            findings=(
                LiveFinding(
                    claim="Validation records a mismatch; cause remains uncertain.",
                    status="SUPPORTED",
                    evidence_ids=(identifier,),
                    assertions=(
                        LiveAssertion(
                            evidence_id=identifier,
                            field_path="/rules/0/expected_amount",
                            value=rule["expected_amount"],
                            currency=rule["currency"],
                        ),
                    ),
                ),
            ),
            proposed_action="REQUEST_EVIDENCE",
            resolution_rationale="Reconcile original records.",
            uncertainties=("Original document arithmetic has not been independently verified.",),
            limitations=("Recorded extraction is not proof of original-document authenticity.",),
        )
        return self._turn(draft=candidate)

    def critic(self, draft, delivered, *, timeout_seconds, max_output_tokens):
        return self._turn(verdict=LiveCritic(accepted=True))


def test_live_worker_uses_actual_stdio_and_bound_authenticated_run(
    pg_client,
    pg_engine,
    settings,
):
    configure(settings, pg_engine)
    identifier = prepared(pg_client, pg_engine)
    before = financial_state(pg_engine)
    run_id, queued = enqueue(pg_client, identifier, "live-actual-mcp")
    assert queued.json()["mode"] == "gemini"
    with Session(pg_engine) as session:
        run = session.get(InvestigationRun, run_id)
        assert run.requested_user_id is not None and run.requested_session_id is not None
        assert "synthetic-only-not-a-real-provider-key" not in json.dumps(run.snapshot)
    fake = FakeGemini()
    assert run_once(
        pg_client.app.state.session_factory, run_id=run_id, settings=settings, provider=fake
    )
    with Session(pg_engine) as session:
        run = session.get(InvestigationRun, run_id)
        assert run.status == "COMPLETED", run.error_code
        assert run.report["mode"] == "gemini" and run.report["resolution"]["accepted"]
        assert (
            run.report["assertions"][0]["value"] == (run.snapshot["blockers"][0]["expected_amount"])
        )
        events = session.scalars(
            select(InvestigationEvent)
            .where(InvestigationEvent.run_id == run_id)
            .order_by(InvestigationEvent.seq)
        ).all()
        tools = [e for e in events if e.event_type == "TOOL_COMPLETED"]
        assert len({e.details["tool"] for e in tools}) >= 2
        assert any(
            e.event_type == "MODEL_STARTED"
            and e.details.get("kind") == "investigate"
            and tools[0].seq < e.seq < tools[-1].seq
            for e in events
        )
        assert all("2300.0000" not in json.dumps(e.details) for e in events)
    assert fake.turn >= 2
    assert financial_state(pg_engine) == before


def test_budget_unknown_reservation_and_deadline_survive_new_claim(
    pg_client,
    pg_engine,
    settings,
):
    configure(settings, pg_engine)
    settings.investigation_token_budget = 8192
    settings.investigation_max_output_tokens = 2048
    identifier = prepared(pg_client, pg_engine)
    run_id, _ = enqueue(pg_client, identifier, "live-budget-durable")
    factory = pg_client.app.state.session_factory
    claim = claim_next(factory, "first-budget-worker", run_id=run_id)
    first = LiveBudget(factory, claim, settings)
    first_id = first.reserve("investigate", 1000)
    # A config change cannot alter an already reserved run after recovery.
    settings.investigation_max_output_tokens = 256
    with Session(pg_engine) as session, session.begin():
        run = session.get(InvestigationRun, run_id)
        deadline = run.budget_metadata["deadline"]
        assert run.budget_metadata["calls"][0]["usage"] is None
        run.lease_until = database_now(session) - timedelta(seconds=1)
    second_claim = claim_next(factory, "recovery-budget-worker", run_id=run_id)
    assert second_claim.fence > claim.fence
    recovered = LiveBudget(factory, second_claim, settings)
    recovered.reserve("draft", 1000)
    with pytest.raises(LiveLimitError, match="MODEL_BUDGET"):
        recovered.reserve("critic", 1000)
    with Session(pg_engine) as session:
        run = session.get(InvestigationRun, run_id)
        assert run.budget_metadata["deadline"] == deadline
        assert run.budget_metadata["calls"][0]["id"] == first_id
        assert sum(c["charged"] for c in run.budget_metadata["calls"]) == 6096
    recovered.reconcile(first_id, usage={"total_tokens": 70})
    output_limits = []

    def operation(timeout, output):
        output_limits.append(output)
        return FakeGemini._turn()

    recovered.call(
        "critic", {}, operation, lambda: None, estimator=lambda payload, timeout_seconds: 128
    )
    assert output_limits == [2048]
    with Session(pg_engine) as session:
        run = session.get(InvestigationRun, run_id)
        assert run.budget_metadata["calls"][-1]["reserved"] == 128 + 2048
        assert run.budget_metadata["calls"][1]["usage"] is None
        assert run.budget_metadata["calls"][1]["charged"] == 3048
    with pytest.raises(LiveLimitError, match="INVESTIGATION_MODEL_BUDGET"):
        recovered.call(
            "draft",
            {},
            operation,
            lambda: None,
            estimator=lambda payload, timeout_seconds: 50000,
        )
    assert output_limits == [2048]  # No model request happened on budget rejection.
    with Session(pg_engine) as session:
        exhausted = session.scalar(
            select(InvestigationEvent).where(
                InvestigationEvent.run_id == run_id,
                InvestigationEvent.event_type == "BUDGET_EXHAUSTED",
            )
        )
        assert exhausted.details == {"resource": "tokens", "kind": "draft"}


def test_provider_diagnostics_and_bounded_retry_are_persisted(
    pg_client,
    pg_engine,
    settings,
    monkeypatch,
):
    from app.modules.investigation.gemini_provider import GeminiInvestigationError

    configure(settings, pg_engine)
    identifier = prepared(pg_client, pg_engine)
    run_id, _ = enqueue(pg_client, identifier, "diagnostics-only")
    factory = pg_client.app.state.session_factory
    claim = claim_next(factory, "diagnostics-worker", run_id=run_id)
    budget = LiveBudget(factory, claim, settings)
    attempts, sleeps = [], []
    monkeypatch.setattr("app.modules.investigation.budgets.time.sleep", sleeps.append)
    monkeypatch.setattr("app.modules.investigation.budgets.random.uniform", lambda *args: 0)
    diagnostics = {"http_status": 429, "retryable": True, "retry_after_seconds": 12.0}

    def operation(timeout, output):
        attempts.append(output)
        if len(attempts) == 1:
            raise GeminiInvestigationError(
                "GEMINI_RATE_LIMITED", retryable=True, diagnostics=diagnostics
            )
        return FakeGemini._turn()

    budget.call("investigate", {}, operation, lambda: None)
    assert len(attempts) == 2 and sleeps == [1]
    with Session(pg_engine) as session:
        run = session.get(InvestigationRun, run_id)
        assert run.budget_metadata["steps"] == 1
        assert run.budget_metadata["calls"][0]["provider_diagnostics"] == diagnostics
        assert run.budget_metadata["calls"][0]["usage"] is None
        events = session.scalars(
            select(InvestigationEvent).where(InvestigationEvent.run_id == run_id)
        ).all()
        failed = next(e for e in events if e.event_type == "MODEL_FAILED")
        assert failed.details["provider_error_code"] == "GEMINI_RATE_LIMITED"
        assert failed.details["provider_diagnostics"] == diagnostics
        retry = next(e for e in events if e.event_type == "MODEL_RETRY_SCHEDULED")
        assert retry.details["failed_attempt"] == 1
        assert retry.details["next_attempt"] == 2
        assert retry.details["backoff_seconds"] == 1


def test_logout_during_model_request_prevents_tools_and_publication(
    pg_client,
    pg_engine,
    settings,
):
    configure(settings, pg_engine)
    identifier = prepared(pg_client, pg_engine)
    before = financial_state(pg_engine)
    run_id, _ = enqueue(pg_client, identifier, "live-logout")

    def logout():
        response = pg_client.post("/api/v1/auth/logout", **operator_auth(pg_client))
        assert response.status_code == 204

    assert not run_once(
        pg_client.app.state.session_factory,
        run_id=run_id,
        settings=settings,
        provider=FakeGemini(on_first=logout),
    )
    with Session(pg_engine) as session:
        run = session.get(InvestigationRun, run_id)
        assert run.status == "FAILED" and run.report is None
        assert not session.scalar(
            select(InvestigationEvent).where(
                InvestigationEvent.run_id == run_id, InvestigationEvent.event_type == "TOOL_STARTED"
            )
        )
    assert financial_state(pg_engine) == before


@pytest.mark.parametrize("failure_code", [None, "INVESTIGATION_DEADLINE", "MCP_UNAUTHORIZED"])
def test_closed_mcp_never_falls_back_to_in_process_evidence(
    pg_client,
    pg_engine,
    settings,
    failure_code,
):
    configure(settings, pg_engine)
    identifier = prepared(pg_client, pg_engine)
    before = financial_state(pg_engine)
    run_id, _ = enqueue(pg_client, identifier, "live-mcp-closed")
    fake = FakeGemini()

    class ClosedMCP:
        def __init__(self, *args):
            pass

        def __enter__(self):
            if failure_code:
                from app.core.errors import AppError

                raise AppError(403, failure_code, "Synthetic authorization failure")
            raise RuntimeError("SYNTHETIC_MCP_CLOSED")

        def __exit__(self, *args):
            return False

    assert not run_once(
        pg_client.app.state.session_factory,
        run_id=run_id,
        settings=settings,
        provider=fake,
        mcp_factory=ClosedMCP,
    )
    assert fake.turn == 0
    with Session(pg_engine) as session:
        run = session.get(InvestigationRun, run_id)
        assert run.status == "FAILED" and run.report is None
        assert run.error_code == (failure_code or "INVESTIGATION_FAILED")
    assert financial_state(pg_engine) == before


def test_critic_cannot_accept_fabricated_reference_after_bounded_repairs(
    pg_client,
    pg_engine,
    settings,
):
    configure(settings, pg_engine)
    identifier = prepared(pg_client, pg_engine)
    before = financial_state(pg_engine)
    run_id, _ = enqueue(pg_client, identifier, "live-forged-grounding")
    completed = run_once(
        pg_client.app.state.session_factory,
        run_id=run_id,
        settings=settings,
        provider=FakeGemini(invalid=True),
    )
    with Session(pg_engine) as session:
        run = session.get(InvestigationRun, run_id)
        safe_events = [
            (
                e.event_type,
                {
                    k: v
                    for k, v in e.details.items()
                    if k in {"error_type", "error_code", "error_site", "next_nodes"}
                },
            )
            for e in session.scalars(
                select(InvestigationEvent)
                .where(InvestigationEvent.run_id == run_id)
                .order_by(InvestigationEvent.seq)
            )
        ]
        assert completed, {"status": run.status, "code": run.error_code, "events": safe_events}
        assert run.status == "FAILED"
        assert run.error_code == "INVESTIGATION_INVALID_EVIDENCE_REFERENCES"
        assert not run.report["resolution"]["accepted"]
        assert "invented-reference" not in json.dumps(run.report)
        assert not run.report["assertions"]
    response = pg_client.get(f"/api/v1/investigations/{run_id}", **operator_auth(pg_client))
    assert response.json()["status"] == "FAILED"
    assert response.json()["applicable"] is False
    assert response.json()["report"] is None
    assert financial_state(pg_engine) == before


@pytest.mark.parametrize("attack", ["cross_invoice_arguments", "financial_write_tool"])
def test_model_cannot_supply_cross_invoice_arguments_or_financial_write_tools(
    pg_client,
    pg_engine,
    settings,
    attack,
):
    configure(settings, pg_engine)
    identifier = prepared(pg_client, pg_engine)
    before = financial_state(pg_engine)
    run_id, _ = enqueue(pg_client, identifier, "live-unsafe-arguments")
    assert not run_once(
        pg_client.app.state.session_factory,
        run_id=run_id,
        settings=settings,
        provider=FakeGemini(
            unsafe_args=attack == "cross_invoice_arguments",
            unsafe_tool=attack == "financial_write_tool",
        ),
    )
    with Session(pg_engine) as session:
        run = session.get(InvestigationRun, run_id)
        assert run.status == "FAILED" and run.report is None
    assert financial_state(pg_engine) == before


def test_public_demonstration_rejects_live_model_configuration():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, public_demo=True, investigation_mode="gemini")
