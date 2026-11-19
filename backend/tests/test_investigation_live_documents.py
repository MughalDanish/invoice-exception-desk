"""Document-bearing live checkpoints with real PostgreSQL and stdio MCP."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import InvestigationEvent, InvestigationRun, Invoice
from app.modules.investigation.live_schemas import ModelToolCall, ProtocolContent, ProtocolPart
from app.modules.investigation.worker import run_once
from tests.test_investigation import financial_state, prepared
from tests.test_investigation_durable import enqueue
from tests.test_investigation_live import FakeGemini, configure
from tests.test_investigation_parallel import evidence


class DocumentGemini(FakeGemini):
    def step(self, history, definitions, *, timeout_seconds, max_output_tokens):
        if self.turn == 0:
            self.turn += 1
            calls = tuple(
                ModelToolCall(id=None, name=name, args={})
                for name in ("get_invoice_snapshot", "get_rule_results", "get_supporting_documents")
            )
            return self._turn(
                content=ProtocolContent(
                    role="model", parts=tuple(ProtocolPart(function_call=c) for c in calls)
                ),
                calls=calls,
            )
        return super().step(
            history,
            definitions,
            timeout_seconds=timeout_seconds,
            max_output_tokens=max_output_tokens,
        )


def test_document_rich_tool_results_survive_checkpoint_and_next_model_turn(
    pg_client, pg_engine, settings
):
    configure(settings, pg_engine)
    identifier = prepared(pg_client, pg_engine)
    with Session(pg_engine) as session, session.begin():
        invoice = session.get(Invoice, uuid.UUID(identifier))
        session.add(
            evidence(
                invoice.id,
                invoice.normalized_vendor_name,
                content="Synthetic purchase-order record RECORD-RANDOM. "
                "The purchase-order amendment is present and describes an additional service fee. "
                "It does not establish original invoice arithmetic or authorize payment.",
            )
        )
    before = financial_state(pg_engine)
    run_id, _ = enqueue(pg_client, identifier, "live-documents")
    provider = DocumentGemini()
    assert run_once(
        pg_client.app.state.session_factory,
        run_id=run_id,
        settings=settings,
        provider=provider,
    )
    with Session(pg_engine) as session:
        run = session.get(InvestigationRun, run_id)
        events = session.scalars(
            select(InvestigationEvent)
            .where(InvestigationEvent.run_id == run_id)
            .order_by(InvestigationEvent.seq)
        ).all()
        assert run.status == "COMPLETED", (run.error_code, [e.details for e in events])
        assert provider.turn >= 2
        assert any(
            e.event_type == "MODEL_STARTED"
            and e.details.get("kind") == "investigate"
            and e.seq
            > next(
                e.seq
                for e in events
                if e.event_type == "TOOL_COMPLETED"
                and e.details["tool"] == "get_supporting_documents"
            )
            for e in events
        )
    assert financial_state(pg_engine) == before
