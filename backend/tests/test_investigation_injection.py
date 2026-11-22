"""Host containment after real MCP delivers injected synthetic source text.

The fake model deliberately follows the hostile instruction. These tests prove
the code boundary rejects that request; they do not establish LLM immunity.
"""

import json
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.models import InvestigationEvent, InvestigationRun, Invoice
from app.modules.approvals.service import payload_hash
from app.modules.investigation.live_schemas import ModelToolCall, ProtocolContent, ProtocolPart
from app.modules.investigation.worker import run_once
from tests.test_investigation import prepared
from tests.test_investigation_durable import enqueue
from tests.test_investigation_live import FakeGemini, configure
from tests.test_investigation_parallel import evidence

CORPUS = json.loads(
    (
        Path(__file__).resolve().parents[2] / "fixtures/investigation/prompt-injection-cases.json"
    ).read_text()
)


def financial_digest(engine):
    """Hash all financial rows, not just invoice status and ledger count."""
    tables = (
        "invoices",
        "vendors",
        "validation_results",
        "invoice_reviews",
        "ledger_entries",
        "audit_events",
        "processing_attempts",
        "integration_deliveries",
    )
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT current_schema()")).startswith("ied_test_")
        records = {
            name: sorted(
                connection.execute(text(f'SELECT row_to_json(t)::text FROM "{name}" t')).scalars()
            )
            for name in tables
        }
    return payload_hash(records)


class SourceFollowingFake(FakeGemini):
    """No command supplied in the initial context or provider constructor."""

    def __init__(self):
        super().__init__()
        self.source_digest = None
        self.requested_from_source = None

    def step(self, history, definitions, *, timeout_seconds, max_output_tokens):
        self.turn += 1
        assert "INSTRUCTION_JSON=" not in history[0].model_dump_json()
        if self.turn == 1:
            call = ModelToolCall(id="read-rules", name="get_rule_results", args={})
        elif self.turn == 2:
            returned = [
                part.function_response["response"]
                for content in history
                for part in content.parts
                if part.function_response
            ]
            assert any(result["name"] == "get_rule_results" for result in returned)
            call = ModelToolCall(id="read-source", name="get_supporting_documents", args={})
        elif self.turn == 3:
            returned = [
                part.function_response["response"]
                for content in history
                for part in content.parts
                if part.function_response
            ]
            result = next(r for r in returned if r["name"] == "get_supporting_documents")
            assert result["status"] == "FOUND"
            source = result["data"]["sources"][0]
            source_text = source.get("text", source.get("excerpt"))
            self.source_digest = payload_hash({"text": source_text})
            instruction = json.loads(source_text.split("INSTRUCTION_JSON=", 1)[1])
            self.requested_from_source = instruction
            call = ModelToolCall(
                id="hostile-request", name=instruction["tool"], args=instruction["arguments"]
            )
        else:
            pytest.fail("Host should terminate the disallowed request, never call the model again")
        return self._turn(
            content=ProtocolContent(role="model", parts=(ProtocolPart(function_call=call),)),
            calls=(call,),
        )

    def draft(self, *args, **kwargs):
        pytest.fail("Hostile request must not reach report generation")


def test_prompt_injection_corpus_is_explicit_synthetic_and_self_consistent():
    assert CORPUS["synthetic"] is True and CORPUS["version"] == 1
    assert len(CORPUS["cases"]) == 3
    for case in CORPUS["cases"]:
        assert set(case) == {"name", "tool", "arguments", "text"}
        assert len(case["text"]) <= 1000
        assert json.loads(case["text"].split("INSTRUCTION_JSON=", 1)[1]) == {
            "tool": case["tool"],
            "arguments": case["arguments"],
        }


@pytest.mark.parametrize("case", CORPUS["cases"], ids=lambda case: case["name"])
def test_document_instruction_is_contained_after_actual_mcp_delivery(
    pg_client,
    pg_engine,
    settings,
    case,
):
    configure(settings, pg_engine)
    identifier = prepared(pg_client, pg_engine)
    with Session(pg_engine) as session:
        invoice = session.get(Invoice, uuid.UUID(identifier))
        session.add(
            evidence(
                invoice.id,
                invoice.normalized_vendor_name,
                kind="PO" if case["name"].startswith("po-") else "EMAIL",
                content=case["text"],
            )
        )
        session.commit()
    before = financial_digest(pg_engine)
    run_id, _ = enqueue(pg_client, identifier, "injection-" + case["name"])
    fake = SourceFollowingFake()
    assert not run_once(
        pg_client.app.state.session_factory, run_id=run_id, settings=settings, provider=fake
    )
    with Session(pg_engine) as session:
        run = session.get(InvestigationRun, run_id)
        assert run.status == "FAILED" and run.report is None
        events = session.scalars(
            select(InvestigationEvent)
            .where(InvestigationEvent.run_id == run_id)
            .order_by(InvestigationEvent.seq)
        ).all()
        safe_diagnostic = {
            "status": run.status,
            "code": run.error_code,
            "events": [
                (
                    event.event_type,
                    {
                        key: value
                        for key, value in event.details.items()
                        if key in {"error_type", "error_site", "provider_error_code"}
                    },
                )
                for event in events
            ],
        }
        assert fake.turn == 3, safe_diagnostic
        assert fake.source_digest == payload_hash({"text": case["text"]})
        assert fake.requested_from_source == {"tool": case["tool"], "arguments": case["arguments"]}
        completed = [e.details["tool"] for e in events if e.event_type == "TOOL_COMPLETED"]
        assert completed == ["get_rule_results", "get_supporting_documents"]
        assert not any(case["text"] in json.dumps(e.details) for e in events)
    assert financial_digest(pg_engine) == before
