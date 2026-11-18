"""Supervisor safety gates and invoice/supplier-scoped, read-only evidence tools."""

import json
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Invoice, Vendor
from app.modules.investigation.graph import build_graph
from app.modules.investigation.providers import MockInvestigationProvider
from app.modules.investigation.routing import mandatory_plan, validate_plan
from app.modules.investigation.schemas import (
    InvestigationPlan,
    LookupSnapshot,
    RuleEvidence,
    SupplierPolicy,
    ToolRequest,
)
from app.modules.investigation.tools import ReadOnlyTools
from tests.conftest import operator_auth
from tests.test_investigation import financial_state, investigate, prepared, snapshot
from tests.test_processing import process, seed, upload_fixture


def mixed_snapshot():
    s = snapshot()
    return s.model_copy(
        update={
            "blockers": tuple(
                RuleEvidence(
                    id=uuid.uuid4(),
                    code=code,
                    expected_amount="2300.0000",
                    observed_amount="2500.0000",
                )
                for code in (
                    "TOTAL_MISMATCH",
                    "DUPLICATE_INVOICE",
                    "UNAPPROVED_VENDOR",
                    "AMOUNT_OUTLIER",
                )
            ),
            "lookup": LookupSnapshot(
                supplier_key="beta tech",
                invoice_key="b-002",
                invoice_total="2500.0000",
                policy=SupplierPolicy(
                    id=uuid.uuid4(), approved=False, currency="USD", amount_limit="2000.0000"
                ),
            ),
        }
    )


@pytest.mark.parametrize(
    "code,role,kind,tool",
    [
        ("TOTAL_MISMATCH", "financial", "arithmetic", "get_invoice_snapshot"),
        ("DUPLICATE_INVOICE", "financial", "duplicate", "find_duplicate_candidates"),
        ("UNAPPROVED_VENDOR", "supplier", "supplier", "get_supplier_policy"),
        ("AMOUNT_OUTLIER", "supplier", "outlier", "get_supplier_history"),
    ],
)
def test_four_blocker_classes_have_mandatory_routes(code, role, kind, tool):
    s = mixed_snapshot()
    task = next(
        t
        for t in mandatory_plan(s).tasks
        if next(r for r in s.blockers if r.id == t.rule_id).code == code
    )
    assert task.role == role and task.kind == kind and tool in task.tools


@pytest.mark.parametrize(
    "mutation",
    [
        "omit",
        "duplicate",
        "wrong_role",
        "wrong_rule",
        "unknown_tool",
        "write_tool",
        "missing_tool",
        "free_args",
    ],
)
def test_invalid_plan_rejected_before_any_tool_or_worker_runs(mutation, monkeypatch):
    s = mixed_snapshot()
    proposed = mandatory_plan(s).model_dump(mode="json")
    tasks = proposed["tasks"]
    if mutation == "omit":
        tasks.pop()
    elif mutation == "duplicate":
        tasks.append(tasks[0])
    elif mutation == "wrong_role":
        tasks[0]["role"] = "supplier"
    elif mutation == "wrong_rule":
        tasks[0]["rule_id"] = str(uuid.uuid4())
    elif mutation == "unknown_tool":
        tasks[0]["tools"] = ["run_sql"]
    elif mutation == "write_tool":
        tasks[0]["tools"] = ["post_invoice"]
    elif mutation == "missing_tool":
        tasks[0]["tools"] = ["get_rule_results"]
    else:
        tasks[0]["invoice_id"] = str(uuid.uuid4())

    class BadSupervisor(MockInvestigationProvider):
        def plan(self, snapshot):
            return InvestigationPlan.model_validate_json(json.dumps(proposed))

    monkeypatch.setattr(
        ReadOnlyTools, "call", lambda *a: pytest.fail("Tool ran before plan validation")
    )
    with pytest.raises(ValueError):
        build_graph(BadSupervisor()).invoke(
            {"run_id": uuid.uuid4(), "snapshot": s, "findings": {}}, config={"recursion_limit": 12}
        )


def test_dynamic_routing_respects_safe_plan_order_and_deduplicates_tools():
    class Reordered(MockInvestigationProvider):
        def plan(self, s):
            return InvestigationPlan(tasks=tuple(reversed(mandatory_plan(s).tasks)))

    s = mixed_snapshot()
    assert validate_plan(s, Reordered().plan(s))
    updates = list(
        build_graph(Reordered()).stream(
            {"run_id": uuid.uuid4(), "snapshot": s, "findings": {}},
            config={"recursion_limit": 12},
            stream_mode="updates",
        )
    )
    nodes = [next(iter(update)) for update in updates]
    assert nodes.index("supplier") < nodes.index("financial")
    report = updates[-1]["advisory_report"]["report"]
    assert len(report.findings) == 4
    assert len(report.tools_used) == 5 and len(set(report.tools_used)) == 5
    assert len(report.plan.tasks) == 4
    assert all(f.status == "SUPPORTED" for f in report.findings)
    assert "2000.0000 USD" in next(f.claim for f in report.findings if "AMOUNT_OUTLIER" in f.claim)


@pytest.mark.parametrize("attack", ["invoice", "supplier", "sql", "path", "write"])
def test_tool_arguments_reject_scope_spoofing_or_arbitrary_access(attack):
    s = mixed_snapshot()
    request = dict(
        name="get_supplier_policy", invoice_id=s.invoice_id, supplier_key=s.lookup.supplier_key
    )
    if attack == "invoice":
        request["invoice_id"] = uuid.uuid4()
    elif attack == "supplier":
        request["supplier_key"] = "another supplier"
    elif attack == "sql":
        request["sql"] = "SELECT * FROM invoices"
    elif attack == "path":
        request["path"] = "../../.env"
    else:
        request["name"] = "approve_supplier"
    with pytest.raises(ValueError):
        ReadOnlyTools(s).call(ToolRequest(**request))


def test_missing_currency_does_not_invent_comparable_outlier_evidence():
    s = mixed_snapshot().model_copy(update={"currency": "JPY"})
    result = build_graph(MockInvestigationProvider()).invoke(
        {"run_id": uuid.uuid4(), "snapshot": s, "findings": {}}, config={"recursion_limit": 12}
    )
    finding = next(f for f in result["report"].findings if "comparable currency" in f.claim)
    assert finding.status == "INSUFFICIENT"


def test_unknown_blocker_is_not_ignored_and_old_reports_still_parse():
    from app.modules.investigation.schemas import InvestigationReport

    s = snapshot().model_copy(
        update={"blockers": (RuleEvidence(id=uuid.uuid4(), code="FUTURE_RULE"),)}
    )
    result = build_graph(MockInvestigationProvider()).invoke(
        {"run_id": uuid.uuid4(), "snapshot": s, "findings": {}}, config={"recursion_limit": 12}
    )
    assert result["report"].findings[0].status == "INSUFFICIENT"
    legacy = result["report"].model_dump(mode="json")
    for key in ("plan", "tools_used", "lookup_digest"):
        legacy.pop(key)
    assert InvestigationReport.model_validate_json(json.dumps(legacy)).plan is None


@pytest.mark.postgres
@pytest.mark.parametrize(
    "case,code,tool",
    [
        ("wrong-total.pdf", "TOTAL_MISMATCH", "get_invoice_snapshot"),
        ("unknown-vendor-1.pdf", "UNAPPROVED_VENDOR", "get_supplier_policy"),
        ("duplicate-altered.pdf", "DUPLICATE_INVOICE", "find_duplicate_candidates"),
        ("outlier", "AMOUNT_OUTLIER", "get_supplier_history"),
    ],
)
def test_real_db_four_routes_are_scoped_and_leave_financial_records_unchanged(
    pg_client, pg_engine, case, code, tool
):
    seed(pg_engine)
    if case == "duplicate-altered.pdf":
        assert process(pg_client, upload_fixture(pg_client, "clean-001.pdf")).status_code == 200
    if case == "outlier":
        with Session(pg_engine) as db:
            for vendor in db.scalars(select(Vendor)):
                vendor.baseline_amount_limit = "100.00"
            db.commit()
        case = "clean-001.pdf"
    identifier = upload_fixture(pg_client, case)
    assert process(pg_client, identifier).status_code == 200
    before = financial_state(pg_engine)
    result = investigate(pg_client, identifier).json()
    assert result["status"] == "COMPLETED"
    report = result["report"]
    assert tool in report["tools_used"]
    with Session(pg_engine) as db:
        from app.db.models import InvestigationRun, ValidationResult

        row = db.scalar(select(InvestigationRun))
        ids = {
            str(r.id)
            for r in db.scalars(
                select(ValidationResult).where(
                    ValidationResult.invoice_id == uuid.UUID(identifier),
                    ValidationResult.rule_code == code,
                    ValidationResult.run_id
                    == db.get(Invoice, uuid.UUID(identifier)).validation_run_id,
                )
            )
        }
        assert any(t["rule_id"] in ids for t in report["plan"]["tasks"])
        lookup = row.snapshot["lookup"]
        assert all(c["id"] != identifier for c in lookup["duplicates"])
        if code == "UNAPPROVED_VENDOR":
            assert lookup["policy"] is None
    assert financial_state(pg_engine) == before


@pytest.mark.postgres
def test_supplier_policy_change_invalidates_saved_report_without_invoice_edit(pg_client, pg_engine):
    identifier = prepared(pg_client, pg_engine)
    report = investigate(pg_client, identifier).json()
    with Session(pg_engine) as db:
        invoice = db.get(Invoice, uuid.UUID(identifier))
        vendor = db.get(Vendor, invoice.vendor_id)
        vendor.is_approved = False
        db.commit()
    before = financial_state(pg_engine)
    result = pg_client.get(
        f"/api/v1/investigations/{report['run_id']}", **operator_auth(pg_client)
    ).json()
    assert result["status"] == "STALE" and result["report"] is None
    assert financial_state(pg_engine) == before


@pytest.mark.postgres
def test_invalid_supervisor_plan_fails_safely_without_financial_effects(
    pg_client, pg_engine, monkeypatch
):
    identifier = prepared(pg_client, pg_engine)
    before = financial_state(pg_engine)
    monkeypatch.setattr(MockInvestigationProvider, "plan", lambda *args: {"tasks": []})
    result = investigate(pg_client, identifier).json()
    assert result["status"] == "FAILED" and result["error_code"] == "INVESTIGATION_FAILED"
    assert financial_state(pg_engine) == before


@pytest.mark.postgres
def test_policy_change_during_graph_is_stale_before_publish(pg_client, pg_engine, monkeypatch):
    identifier = prepared(pg_client, pg_engine)
    original = MockInvestigationProvider.investigate

    def change_policy(self, s, *args):
        with Session(pg_engine) as db:
            vendor = db.get(Vendor, s.lookup.policy.id)
            vendor.is_approved = not vendor.is_approved
            db.commit()
        return original(self, s, *args)

    monkeypatch.setattr(MockInvestigationProvider, "investigate", change_policy)
    result = investigate(pg_client, identifier).json()
    assert result["status"] == "STALE" and result["report"] is None


@pytest.mark.postgres
def test_read_projection_excludes_other_suppliers_and_invoice_identities(pg_client, pg_engine):
    from app.db.models import InvestigationRun

    seed(pg_engine)
    first = upload_fixture(pg_client, "clean-001.pdf")
    assert process(pg_client, first).status_code == 200
    assert (
        pg_client.post(
            f"/api/v1/invoices/{first}/post",
            **operator_auth(pg_client),
            json={"expected_revision": 1},
        ).status_code
        == 200
    )
    identifier = upload_fixture(pg_client, "wrong-total.pdf")
    assert process(pg_client, identifier).status_code == 200
    before = financial_state(pg_engine)
    result = investigate(pg_client, identifier).json()
    assert result["status"] == "COMPLETED"
    with Session(pg_engine) as db:
        row = db.scalar(select(InvestigationRun))
        assert row.snapshot["lookup"]["history"] == []
        assert row.snapshot["lookup"]["ledger_matches"] == []
        assert row.snapshot["lookup"]["duplicates"] == []
    assert financial_state(pg_engine) == before


@pytest.mark.postgres
def test_new_exact_duplicate_invalidates_previous_report(pg_client, pg_engine):
    identifier = prepared(pg_client, pg_engine, "wrong-total.pdf")
    report = investigate(pg_client, identifier).json()
    with Session(pg_engine) as db:
        source = db.get(Invoice, uuid.UUID(identifier))
        import copy

        peer = Invoice(
            source=source.source,
            filename="synthetic-peer.pdf",
            mime_type=source.mime_type,
            byte_size=source.byte_size,
            sha256=uuid.uuid4().hex * 2,
            file_path="synthetic-test-only",
            status=source.status,
            revision=1,
            normalized_vendor_name=source.normalized_vendor_name,
            normalized_invoice_number=source.normalized_invoice_number,
            current_data=copy.deepcopy(source.current_data),
        )
        db.add(peer)
        db.commit()
    result = pg_client.get(
        f"/api/v1/investigations/{report['run_id']}", **operator_auth(pg_client)
    ).json()
    assert result["status"] == "STALE" and result["report"] is None


@pytest.mark.postgres
def test_lookup_candidate_sample_is_bounded_and_marked_truncated(pg_client, pg_engine):
    from app.modules.investigation.lookups import capture_lookups

    identifier = prepared(pg_client, pg_engine)
    with Session(pg_engine) as db:
        source = db.get(Invoice, uuid.UUID(identifier))
        for _ in range(22):
            db.add(
                Invoice(
                    source=source.source,
                    filename="synthetic-peer.pdf",
                    mime_type=source.mime_type,
                    byte_size=1,
                    sha256=uuid.uuid4().hex * 2,
                    file_path="synthetic-test-only",
                    status=source.status,
                    revision=1,
                    normalized_vendor_name=source.normalized_vendor_name,
                    normalized_invoice_number=source.normalized_invoice_number,
                )
            )
        db.commit()
        lookup = capture_lookups(db, source)
        assert len(lookup.duplicates) == 20 and lookup.duplicates_truncated is True
