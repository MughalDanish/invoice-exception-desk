"""Day 8: real overlap, stable merge, scoped immutable evidence and abstention."""

import json
import threading
import time
import uuid
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.db.models import InvestigationDocument, InvestigationRun, Invoice
from app.modules.approvals.service import payload_hash
from app.modules.investigation.documents import capture_documents
from app.modules.investigation.graph import build_graph, merge_findings
from app.modules.investigation.providers import MockInvestigationProvider
from app.modules.investigation.routing import mandatory_plan, validate_plan
from app.modules.investigation.schemas import DocumentEvidence, DocumentSnapshot, InvoiceSnapshot
from app.modules.investigation.tools import ReadOnlyTools
from tests.conftest import operator_auth
from tests.test_investigation import financial_state, investigate, prepared
from tests.test_investigation_routing import mixed_snapshot

CORPUS = Path(__file__).resolve().parents[2] / "fixtures/investigation/day-8-corpus.json"


def evidence(invoice_id, supplier, *, source_id=None, version=1, kind="PO", content="Synthetic PO"):
    return InvestigationDocument(
        source_id=source_id or uuid.uuid4(),
        version=version,
        invoice_id=invoice_id,
        supplier_key=supplier,
        kind=kind,
        content=content,
        content_sha256=payload_hash({"text": content}),
    )


def with_documents():
    return mixed_snapshot().model_copy(update={"documents": DocumentSnapshot()})


def run(snapshot, provider=None):
    return build_graph(provider or MockInvestigationProvider()).invoke(
        {"run_id": uuid.uuid4(), "snapshot": snapshot, "findings": {}},
        config={"recursion_limit": 12, "max_concurrency": 3, "callbacks": []},
    )["report"]


def test_three_real_branches_overlap_and_report_waits_for_all(capsys):
    barrier = threading.Barrier(3, timeout=10)
    lock = threading.Lock()
    intervals = {}

    class Timed(MockInvestigationProvider):
        def investigate(self, snapshot, task, results):
            with lock:
                first = task.role not in intervals
                if first:
                    intervals[task.role] = [time.perf_counter(), None]
            if first:
                # Sequential execution cannot satisfy this barrier.
                barrier.wait()
                time.sleep(0.05)
            result = super().investigate(snapshot, task, results)
            with lock:
                intervals[task.role][1] = time.perf_counter()
            return result

    report = run(with_documents(), Timed())
    assert set(intervals) == {"financial", "supplier", "documents"}
    overlap = min(v[1] for v in intervals.values()) - max(v[0] for v in intervals.values())
    assert overlap > 0
    assert len(report.findings) == 5
    print(f"Three-branch measured overlap: {overlap:.6f} seconds")


def test_parallel_merge_is_order_independent_and_conflicts_fail_closed():
    s = with_documents()
    report = run(s)
    findings = {f.task_id: f for f in report.findings}
    for ordered in (list(findings.items()), list(reversed(findings.items()))):
        merged = {}
        for key, value in ordered:
            merged = merge_findings(merged, {key: value})
        assert tuple(merged.values()) == report.findings
    f = report.findings[0]
    with pytest.raises(ValueError):
        merge_findings(findings, {f.task_id: f.model_copy(update={"claim": "Forged"})})


def test_shared_tools_are_actually_called_once_including_report_verification(monkeypatch):
    original = ReadOnlyTools.call
    calls = []

    def counted(self, request):
        calls.append(request.name)
        return original(self, request)

    monkeypatch.setattr(ReadOnlyTools, "call", counted)
    report = run(with_documents())
    assert len(calls) == 6 and len(set(calls)) == 6
    assert sorted(calls) == list(report.tools_used)


def test_document_task_cannot_be_skipped_and_absence_is_explicit():
    s = with_documents()
    plan = mandatory_plan(s)
    with pytest.raises(ValueError):
        validate_plan(s, plan.model_copy(update={"tasks": plan.tasks[:-1]}))
    report = run(s)
    finding = next(f for f in report.findings if f.task_id.startswith("documents:"))
    assert finding.status == "INSUFFICIENT"
    assert all(
        any(kind in item for item in report.missing_evidence) for kind in ("PO", "RECEIPT", "EMAIL")
    )
    assert "get_supporting_documents" in report.tools_used


@pytest.mark.parametrize("attack", ["invoice", "supplier", "hash", "duplicate"])
def test_frozen_document_scope_and_hash_are_validated(attack):
    s = with_documents()
    doc = DocumentEvidence(
        source_id=uuid.uuid4(),
        version=1,
        invoice_id=s.invoice_id,
        supplier_key=s.lookup.supplier_key,
        kind="EMAIL",
        text="untrusted",
        content_sha256=payload_hash({"text": "untrusted"}),
    )
    if attack == "invoice":
        doc = doc.model_copy(update={"invoice_id": uuid.uuid4()})
    elif attack == "supplier":
        doc = doc.model_copy(update={"supplier_key": "other supplier"})
    elif attack == "hash":
        doc = doc.model_copy(update={"content_sha256": "0" * 64})
    items = (doc, doc) if attack == "duplicate" else (doc,)
    with pytest.raises(ValidationError):
        InvoiceSnapshot.model_validate(
            s.model_copy(update={"documents": DocumentSnapshot(items=items)})
        )


def test_conflicting_and_injection_text_never_becomes_financial_authority():
    s = with_documents()
    corpus = json.loads(CORPUS.read_text())
    docs = tuple(
        DocumentEvidence(
            source_id=uuid.UUID(d["source_id"]),
            version=d["version"],
            invoice_id=s.invoice_id,
            supplier_key=s.lookup.supplier_key,
            kind=d["kind"],
            text=d["text"],
            content_sha256=payload_hash({"text": d["text"]}),
        )
        for d in corpus["sources"]
    )
    report = run(s.model_copy(update={"documents": DocumentSnapshot(items=docs)}))
    finding = next(f for f in report.findings if f.task_id.startswith("documents:"))
    assert finding.status == "INSUFFICIENT"
    assert "not been reconciled" in finding.claim
    assert "ignore all previous" not in report.model_dump_json()
    assert report.advisory_only and report.proposed_action == "REQUEST_EVIDENCE"


@pytest.mark.postgres
def test_capture_is_bounded_latest_version_and_scoped_to_both_identities(pg_client, pg_engine):
    identifier = prepared(pg_client, pg_engine)
    with Session(pg_engine) as db:
        invoice = db.get(Invoice, uuid.UUID(identifier))
        other = Invoice(
            id=uuid.uuid4(),
            **{
                c.name: getattr(invoice, c.name)
                for c in Invoice.__table__.columns
                if c.name not in {"id", "created_at", "sha256"}
            },
            sha256="f" * 64,
        )
        db.add(other)
        db.flush()
        source_id = uuid.UUID(int=1)
        db.add_all(
            [
                evidence(invoice.id, invoice.normalized_vendor_name, source_id=source_id),
                evidence(
                    invoice.id,
                    invoice.normalized_vendor_name,
                    source_id=source_id,
                    version=2,
                    content="Latest PO",
                ),
                evidence(invoice.id, "other supplier", content="Foreign supplier secret"),
                evidence(
                    other.id, invoice.normalized_vendor_name, content="Foreign invoice secret"
                ),
            ]
        )
        db.add_all(evidence(invoice.id, invoice.normalized_vendor_name) for _ in range(13))
        db.commit()
        captured = capture_documents(db, invoice)
        assert len(captured.items) == 12 and captured.truncated
        assert next(d for d in captured.items if d.source_id == source_id).version == 2
        assert "Foreign" not in captured.model_dump_json()


@pytest.mark.postgres
def test_evidence_append_makes_report_stale_without_financial_mutation(pg_client, pg_engine):
    identifier = prepared(pg_client, pg_engine)
    before = financial_state(pg_engine)
    first = investigate(pg_client, identifier).json()
    assert first["status"] == "COMPLETED"
    with Session(pg_engine) as db:
        invoice = db.get(Invoice, uuid.UUID(identifier))
        source = evidence(invoice.id, invoice.normalized_vendor_name)
        source_id = source.source_id
        supplier_key = invoice.normalized_vendor_name
        db.add(source)
        db.commit()
    current = pg_client.get(
        f"/api/v1/investigations/{first['run_id']}", **operator_auth(pg_client)
    ).json()
    assert current["status"] == "STALE" and current["report"] is None
    second = investigate(pg_client, identifier, key="after-source-added").json()
    assert second["status"] == "COMPLETED"
    with Session(pg_engine) as db:
        db.add(
            evidence(
                uuid.UUID(identifier),
                supplier_key,
                source_id=source_id,
                version=2,
                content="Revised synthetic supporting evidence",
            )
        )
        db.commit()
    revised = pg_client.get(
        f"/api/v1/investigations/{second['run_id']}", **operator_auth(pg_client)
    ).json()
    assert revised["status"] == "STALE" and revised["report"] is None
    assert financial_state(pg_engine) == before
    with Session(pg_engine) as db:
        stored = db.get(InvestigationRun, uuid.UUID(first["run_id"]))
        assert stored.report == first["report"]


@pytest.mark.postgres
def test_source_append_during_parallel_work_prevents_publication(pg_client, pg_engine, monkeypatch):
    identifier = prepared(pg_client, pg_engine)
    before = financial_state(pg_engine)
    original = MockInvestigationProvider.investigate

    def append_source(self, snapshot, task, results):
        if task.role == "documents":
            with Session(pg_engine) as db:
                db.add(evidence(snapshot.invoice_id, snapshot.lookup.supplier_key))
                db.commit()
        return original(self, snapshot, task, results)

    monkeypatch.setattr(MockInvestigationProvider, "investigate", append_source)
    result = investigate(pg_client, identifier).json()
    assert result["status"] == "STALE" and result["report"] is None
    assert financial_state(pg_engine) == before


@pytest.mark.postgres
@pytest.mark.parametrize("operation", ["UPDATE", "DELETE"])
def test_supporting_sources_are_append_only(pg_client, pg_engine, operation):
    identifier = prepared(pg_client, pg_engine)
    with Session(pg_engine) as db:
        invoice = db.get(Invoice, uuid.UUID(identifier))
        db.add(evidence(invoice.id, invoice.normalized_vendor_name))
        db.commit()
    with pytest.raises(DBAPIError, match="append-only"):
        with pg_engine.begin() as connection:
            query = (
                "UPDATE investigation_documents SET content = 'changed'"
                if operation == "UPDATE"
                else "DELETE FROM investigation_documents"
            )
            connection.execute(text(query))
    with Session(pg_engine) as db:
        assert len(db.scalars(select(InvestigationDocument)).all()) == 1
