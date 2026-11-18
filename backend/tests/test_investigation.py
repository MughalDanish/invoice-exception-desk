"""Day 6: actual graph + isolated PostgreSQL + unchanged financial records."""

import json
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import (
    AuditEvent,
    InvestigationRun,
    Invoice,
    InvoiceReview,
    LedgerEntry,
    ValidationResult,
    Vendor,
)
from app.main import create_app
from app.modules.investigation.graph import build_graph, merge_findings
from app.modules.investigation.providers import MockInvestigationProvider
from app.modules.investigation.schemas import (
    Finding,
    Findings,
    InvestigationReport,
    InvoiceSnapshot,
    RuleEvidence,
    exact_amount,
)
from tests.conftest import operator_auth
from tests.test_processing import process, seed, upload_fixture


def snapshot():
    return InvoiceSnapshot(
        invoice_id=uuid.uuid4(),
        revision=1,
        payload_sha256="a" * 64,
        document_sha256="b" * 64,
        validation_batch_id=uuid.uuid4(),
        currency="USD",
        blockers=(
            RuleEvidence(
                id=uuid.uuid4(),
                code="TOTAL_MISMATCH",
                expected_amount="2300.0000",
                observed_amount="2500.0000",
            ),
        ),
    )


def test_real_graph_is_offline_and_preserves_exact_recorded_amounts(monkeypatch):
    import socket

    monkeypatch.setattr(
        socket.socket, "connect", lambda *a, **k: pytest.fail("Network not allowed")
    )
    s = snapshot()
    result = build_graph(MockInvestigationProvider()).invoke(
        {"run_id": uuid.uuid4(), "snapshot": s, "findings": {}},
        config={"recursion_limit": 5},
    )
    report = result["report"]
    assert "2300.0000 USD" in report.findings[0].claim
    assert "2500.0000 USD" in report.findings[0].claim
    assert report.mode == "mock" and report.advisory_only is True
    assert report.proposed_action == "REQUEST_EVIDENCE"
    assert report.source_payload_hash == s.payload_sha256
    assert report.source_validation_batch == s.validation_batch_id
    assert "original document" in report.missing_evidence[0]


@pytest.mark.parametrize("value", [1.25, 3, "1,200.00", "NaN", "Infinity", "", None])
def test_invalid_or_missing_recorded_amount_is_not_inferred(value):
    assert exact_amount(value) is None


def test_unsupported_blocker_and_missing_evidence_abstain():
    s = snapshot()
    for rule in (
        RuleEvidence(id=uuid.uuid4(), code="UNAPPROVED_VENDOR"),
        RuleEvidence(id=uuid.uuid4(), code="TOTAL_MISMATCH", observed_amount="2500.00"),
    ):
        result = MockInvestigationProvider().investigate(s.model_copy(update={"blockers": (rule,)}))
        assert result.items[0].status == "INSUFFICIENT"
        assert "cannot investigate" in result.items[0].claim


def test_strict_outputs_reject_financial_actions_extra_fields_and_wrong_types():
    s = snapshot()
    result = (
        build_graph(MockInvestigationProvider())
        .invoke({"run_id": uuid.uuid4(), "snapshot": s, "findings": {}})["report"]
        .model_dump(mode="json")
    )
    for patch in (
        {"proposed_action": "POST"},
        {"proposed_action": "APPROVE"},
        {"advisory_only": False},
        {"payment": "send"},
        {"source_revision": "1"},
    ):
        with pytest.raises(ValidationError):
            InvestigationReport.model_validate_json(json.dumps(result | patch))
    with pytest.raises(ValidationError):
        RuleEvidence(id=uuid.uuid4(), code="TOTAL_MISMATCH", expected_amount=2300.0)


def test_reducer_is_deterministic_idempotent_and_rejects_conflicting_ids():
    f = MockInvestigationProvider().investigate(snapshot()).items[0]
    assert merge_findings({f.task_id: f}, {f.task_id: f}) == {f.task_id: f}
    with pytest.raises(ValueError):
        merge_findings({f.task_id: f}, {f.task_id: f.model_copy(update={"claim": "Different"})})
    with pytest.raises(ValueError):
        merge_findings({}, {"forged-id": f})


@pytest.mark.parametrize("kind", ["amount", "citation", "omission", "duplicate"])
def test_graph_rejects_unsupported_or_omitted_claims(kind):
    class BadProvider:
        def investigate(self, s):
            good = MockInvestigationProvider().investigate(s).items[0]
            if kind == "amount":
                return Findings(items=(good.model_copy(update={"claim": "Expected 1 USD"}),))
            if kind == "citation":
                return Findings(
                    items=(good.model_copy(update={"evidence_ids": ("validation:other",)}),)
                )
            if kind == "duplicate":
                return Findings(items=(good, good))
            return Findings(
                items=(
                    Finding(
                        task_id="omitted",
                        claim="No issue",
                        evidence_ids=("invented",),
                        status="SUPPORTED",
                    ),
                )
            )

    with pytest.raises(ValueError):
        build_graph(BadProvider()).invoke(
            {"run_id": uuid.uuid4(), "snapshot": snapshot(), "findings": {}}
        )


def test_investigation_routes_require_operator_not_integration(client):
    identifier = uuid.uuid4()
    assert client.get(f"/api/v1/investigations/{identifier}").status_code == 401
    assert (
        client.post(
            f"/api/v1/invoices/{identifier}/investigations",
            headers={"X-Integration-Key": "integration-key"},
            json={"expected_revision": 1, "idempotency_key": "one"},
        ).status_code
        == 401
    )


def test_public_mode_never_registers_investigation_or_runs_a_graph():
    with TestClient(create_app(Settings(_env_file=None, public_demo=True))) as client:
        identifier = uuid.uuid4()
        assert client.get(f"/api/v1/investigations/{identifier}").status_code == 404
        assert (
            client.post(f"/api/v1/invoices/{identifier}/investigations", json={}).status_code == 403
        )


def financial_state(engine):
    with Session(engine) as db:
        return {
            model.__tablename__: [
                tuple(getattr(row, c.name) for c in model.__table__.columns)
                for row in db.scalars(select(model).order_by(model.id))
            ]
            for model in (Invoice, Vendor, ValidationResult, AuditEvent, InvoiceReview, LedgerEntry)
        }


def prepared(client, engine, name="wrong-total.pdf"):
    seed(engine)
    identifier = upload_fixture(client, name)
    assert process(client, identifier).status_code == 200
    return identifier


def investigate(client, identifier, key="day-6-test", revision=1):
    return client.post(
        f"/api/v1/invoices/{identifier}/investigations",
        **operator_auth(client),
        json={"expected_revision": revision, "idempotency_key": key},
    )


@pytest.mark.postgres
def test_snapshot_to_report_replay_read_and_no_financial_mutation(
    pg_client, pg_engine, monkeypatch
):
    identifier = prepared(pg_client, pg_engine)
    before = financial_state(pg_engine)
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    # Even an accidental host tracing opt-in must not export this financial snapshot.
    import langsmith.client

    monkeypatch.setattr(
        langsmith.client.Client, "create_run", lambda *a, **k: pytest.fail("Trace leaked")
    )
    result = investigate(pg_client, identifier)
    assert result.status_code == 202
    value = result.json()
    assert value["status"] == "COMPLETED" and value["applicable"] is True
    assert value["report"]["proposed_action"] == "REQUEST_EVIDENCE"
    assert value["execution"] == "synchronous_local"
    assert investigate(pg_client, identifier).json()["run_id"] == value["run_id"]
    read = pg_client.get(f"/api/v1/investigations/{value['run_id']}", **operator_auth(pg_client))
    assert read.json() == value
    assert read.headers["cache-control"] == "no-store"
    assert financial_state(pg_engine) == before
    with Session(pg_engine) as db:
        rows = db.scalars(select(InvestigationRun)).all()
        assert len(rows) == 1 and rows[0].requested_by == "operator"
        assert rows[0].snapshot["payload_sha256"] == value["report"]["source_payload_hash"]
        assert "current_data" not in rows[0].snapshot


@pytest.mark.postgres
@pytest.mark.parametrize("change", ["revision", "batch", "payload"])
def test_report_stale_on_every_read_and_key_cannot_rebind(pg_client, pg_engine, change):
    identifier = prepared(pg_client, pg_engine)
    value = investigate(pg_client, identifier).json()
    with Session(pg_engine) as db:
        row = db.get(Invoice, uuid.UUID(identifier))
        if change == "revision":
            row.revision += 1
        elif change == "batch":
            row.validation_run_id = uuid.uuid4()
        else:
            row.current_data = row.current_data | {"total": "2400.00"}
        db.commit()
    before = financial_state(pg_engine)
    read = pg_client.get(
        f"/api/v1/investigations/{value['run_id']}", **operator_auth(pg_client)
    ).json()
    assert read["status"] == "STALE" and not read["applicable"] and read["report"] is None
    assert investigate(pg_client, identifier).status_code == 409
    assert financial_state(pg_engine) == before


@pytest.mark.postgres
def test_concurrent_requests_deduplicate_without_financial_effects(pg_client, pg_engine):
    identifier = prepared(pg_client, pg_engine)
    before = financial_state(pg_engine)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: investigate(pg_client, identifier), range(2)))
    assert all(r.status_code == 202 for r in results)
    assert len({r.json()["run_id"] for r in results}) == 1
    assert financial_state(pg_engine) == before


@pytest.mark.postgres
def test_failure_is_sanitized_and_replay_does_not_retry(pg_client, pg_engine, monkeypatch, caplog):
    identifier = prepared(pg_client, pg_engine)
    before = financial_state(pg_engine)
    calls = []

    def fail(*args):
        calls.append(1)
        raise RuntimeError("secret invoice text MUST_NOT_LOG")

    monkeypatch.setattr(MockInvestigationProvider, "investigate", fail)
    result = investigate(pg_client, identifier).json()
    assert result["status"] == "FAILED" and result["error_code"] == "INVESTIGATION_FAILED"
    assert result["report"] is None
    assert investigate(pg_client, identifier).json() == result
    assert len(calls) == 1
    assert "MUST_NOT_LOG" not in caplog.text + json.dumps(result)
    assert financial_state(pg_engine) == before


@pytest.mark.postgres
def test_change_while_graph_runs_cannot_publish_applicable_report(
    pg_client, pg_engine, monkeypatch
):
    identifier = prepared(pg_client, pg_engine)
    original = MockInvestigationProvider.investigate

    def racing(self, s):
        with Session(pg_engine) as db:
            # Independent transaction succeeds: graph holds no invoice lock/DB transaction.
            db.execute(text("SET LOCAL lock_timeout = '1000ms'"))
            invoice = db.get(Invoice, s.invoice_id)
            invoice.validation_run_id = uuid.uuid4()
            db.commit()
        return original(self, s)

    monkeypatch.setattr(MockInvestigationProvider, "investigate", racing)
    result = investigate(pg_client, identifier).json()
    assert result["status"] == "STALE" and result["report"] is None
    with Session(pg_engine) as db:
        assert not db.scalars(select(LedgerEntry)).all()
        assert not db.scalars(select(InvoiceReview)).all()


@pytest.mark.postgres
def test_eligibility_stale_requests_and_csrf(pg_client, pg_engine):
    identifier = prepared(pg_client, pg_engine, "clean-001.pdf")
    assert investigate(pg_client, identifier).status_code == 409
    wrong = upload_fixture(pg_client, "wrong-total.pdf")
    assert investigate(pg_client, wrong).status_code == 409  # Not extracted yet.
    assert process(pg_client, wrong).status_code == 200
    assert investigate(pg_client, wrong, revision=2).status_code == 409
    response = pg_client.post(
        f"/api/v1/invoices/{wrong}/investigations",
        **operator_auth(pg_client),
        headers={"X-CSRF-Token": "wrong"},
        json={"expected_revision": 1, "idempotency_key": "csrf"},
    )
    assert response.status_code == 403


@pytest.mark.postgres
def test_additive_migration_round_trip_preserves_financial_rows(pg_client, pg_engine):
    from alembic.config import Config

    from alembic import command
    from tests.conftest import ROOT

    prepared(pg_client, pg_engine)
    before = financial_state(pg_engine)
    with pg_engine.begin() as connection:
        config = Config(str(ROOT / "backend/alembic.ini"))
        config.attributes["connection"] = connection
        command.downgrade(config, "0005_cookie_auth")
        command.upgrade(config, "head")
    assert financial_state(pg_engine) == before
