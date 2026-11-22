"""Opt-in, bounded paid Gemini/MCP smoke; ONLY a disposable synthetic QA schema.

No retries of the smoke pair: provider HTTP retries remain within the run budget.
Never run against application invoice rows. No keys, prompts or hidden reasoning
are printed. Review synthetic report artifacts for semantic support separately.
"""

# ruff: noqa: E402 -- repo-local imports require the backend path bootstrap below.

import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from alembic import command
from alembic.config import Config
from app.core.config import Settings
from app.db.models import (
    InvestigationDocument,
    InvestigationEvent,
    InvestigationRun,
    Invoice,
)
from app.main import create_app
from app.modules.approvals.service import payload_hash
from app.modules.auth.bootstrap import bootstrap_operator
from app.modules.investigation.worker import run_once
from app.qa import AUTH, checked, detail, process, upload
from app.seed import seed_vendors
from dotenv import dotenv_values
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session


@contextmanager
def synthetic_live_client(url, key, model):
    schema = "ied_qa_" + uuid.uuid4().hex
    scoped = url.update_query_dict({"options": f"-csearch_path={schema}"})
    admin = create_engine(url, connect_args={"connect_timeout": 5})
    engine = create_engine(scoped, connect_args={"connect_timeout": 5})
    try:
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        with engine.begin() as connection:
            config = Config(str(ROOT / "backend/alembic.ini"))
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        with tempfile.TemporaryDirectory(prefix="ied-live-smoke-") as folder:
            settings = Settings(
                _env_file=None,
                database_url=scoped.render_as_string(hide_password=False),
                auth_jwt_secret="isolated-live-smoke-signing-secret-at-least-32-bytes",
                auth_cookie_secure=False,
                ai_mode="mock",
                investigation_mode="gemini",
                gemini_api_key=key,
                gemini_model=model,
                public_demo=False,
                storage_dir=Path(folder),
                fixtures_dir=ROOT / "fixtures",
            )
            with Session(engine) as session:
                seed_vendors(session)
                bootstrap_operator(session, *AUTH)
            with TestClient(create_app(settings, engine)) as client:
                csrf = checked(client.get("/api/v1/auth/csrf"))["csrf_token"]
                login = checked(
                    client.post(
                        "/api/v1/auth/login",
                        headers={"X-CSRF-Token": csrf},
                        json={"username": AUTH[0], "password": AUTH[1]},
                    )
                )
                client.headers["X-CSRF-Token"] = login["csrf_token"]
                yield client, settings
    finally:
        engine.dispose()
        if not schema.startswith("ied_qa_") or len(schema) != 39:
            raise RuntimeError("UNSAFE_SYNTHETIC_SCHEMA")
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
            remains = connection.scalar(
                text("SELECT count(*) FROM pg_namespace WHERE nspname=:schema"),
                {"schema": schema},
            )
            if remains:
                raise RuntimeError("SYNTHETIC_SCHEMA_CLEANUP_FAILED")
        admin.dispose()


def financial_digest(engine):
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
        if not connection.scalar(text("SELECT current_schema()")).startswith("ied_qa_"):
            raise RuntimeError("SYNTHETIC_SCHEMA_REQUIRED")
        data = {
            table: sorted(
                connection.execute(text(f'SELECT row_to_json(t)::text FROM "{table}" t')).scalars()
            )
            for table in tables
        }
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def run_pair(url, key, model):
    metrics, reports = [], []
    with synthetic_live_client(url, key, model) as (client, settings):
        invoice_id = uuid.UUID(upload(client, "wrong-total.pdf")["invoice_id"])
        process(client, invoice_id)
        record = detail(client, invoice_id)
        if record["status"] != "NEEDS_REVIEW":
            raise RuntimeError("SYNTHETIC_REVIEW_FIXTURE_REQUIRED")
        financial_before = financial_digest(client.app.state.engine)
        source_id = uuid.uuid4()
        marker = "RECORD-" + uuid.uuid4().hex.upper()
        variants = (
            (
                "The purchase-order amendment is present and describes an additional service fee. "
                "It does not establish original invoice arithmetic or authorize payment."
            ),
            (
                "No purchase-order amendment is present. The additional service fee lacks "
                "supporting authorization in this record. "
                "Original invoice arithmetic remains unverified."
            ),
        )
        for index, fact in enumerate(variants, 1):
            source_text = f"Synthetic purchase-order record {marker}. {fact}"
            with Session(client.app.state.engine) as session:
                invoice = session.get(Invoice, invoice_id)
                session.add(
                    InvestigationDocument(
                        source_id=source_id,
                        version=index,
                        invoice_id=invoice_id,
                        supplier_key=invoice.normalized_vendor_name,
                        kind="PO",
                        content=source_text,
                        content_sha256=payload_hash({"text": source_text}),
                    )
                )
                session.commit()
            queued = checked(
                client.post(
                    f"/api/v1/invoices/{invoice_id}/investigations",
                    json={
                        "expected_revision": record["revision"],
                        "idempotency_key": f"live-pair-{index}",
                    },
                ),
                (202,),
            )
            run_id = uuid.UUID(queued["run_id"])
            started = time.monotonic()
            failure = None
            try:
                # Exactly one worker attempt per variant; no cherry-picked repeated pair.
                run_once(client.app.state.session_factory, run_id=run_id, settings=settings)
            except Exception as exc:  # noqa: BLE001 - record type only; never leak provider payloads
                failure = type(exc).__name__
            view = checked(client.get(f"/api/v1/investigations/{run_id}"))
            with Session(client.app.state.engine) as session:
                run = session.get(InvestigationRun, run_id)
                events = session.scalars(
                    select(InvestigationEvent)
                    .where(InvestigationEvent.run_id == run_id)
                    .order_by(InvestigationEvent.seq)
                ).all()
                calls = (run.budget_metadata or {}).get("calls", [])
                tool_names = sorted(
                    {e.details.get("tool") for e in events if e.event_type == "TOOL_COMPLETED"}
                )
                investigation_turns = sum(c.get("kind") == "investigate" for c in calls)
                first_tool = next((e.seq for e in events if e.event_type == "TOOL_COMPLETED"), None)
                later_model = next(
                    (
                        e.seq
                        for e in events
                        if first_tool is not None
                        and e.seq > first_tool
                        and e.event_type == "MODEL_STARTED"
                        and e.details.get("kind") == "investigate"
                    ),
                    None,
                )
                followup_tool = any(
                    later_model is not None
                    and e.seq > later_model
                    and e.event_type == "TOOL_COMPLETED"
                    for e in events
                )
                error_code = run.error_code
            report = view.get("report") or {}
            source_citation = f"source:{source_id}:v{index}:{payload_hash({'text': source_text})}"
            assertions = report.get("assertions", [])
            checks = {
                "completed_live": view["status"] == "COMPLETED" and report.get("mode") == "gemini",
                "accepted_by_code_and_critic": bool(
                    (report.get("resolution") or {}).get("accepted")
                ),
                "at_least_two_distinct_tools": len(tool_names) >= 2,
                "multi_turn_tool_investigation": investigation_turns >= 2,
                "tool_selected_after_prior_result": followup_tool,
                "versioned_source_cited": any(
                    source_citation in f["evidence_ids"] for f in report.get("findings", [])
                ),
                "withheld_source_fact_asserted": any(
                    a.get("evidence_id") == source_citation and a.get("value") == source_text
                    for a in assertions
                ),
                "financial_records_unchanged": financial_digest(client.app.state.engine)
                == financial_before,
            }
            metrics.append(
                {
                    "variant": index,
                    "run_id": str(run_id),
                    "status": view["status"],
                    "model": model,
                    "latency_ms": int((time.monotonic() - started) * 1000),
                    "model_http_attempts": len(calls),
                    "logical_model_steps": (run.budget_metadata or {}).get("steps"),
                    "model_step_limit": ((run.budget_metadata or {}).get("limits") or {}).get(
                        "investigation_max_model_steps"
                    ),
                    "normalized_references": sum(
                        e.details.get("count", 0)
                        for e in events
                        if e.event_type == "REFERENCES_NORMALIZED"
                    ),
                    "reference_rejections": sum(
                        e.event_type == "REPORT_REJECTED"
                        and any(
                            code
                            in {
                                "ASSERTION_PATH_INVALID",
                                "EVIDENCE_NOT_DELIVERED",
                                "ASSERTION_REFERENCE_MISSING",
                            }
                            for code in e.details.get("codes", [])
                        )
                        for e in events
                    ),
                    "report_rejection_codes": [
                        e.details.get("codes", [])
                        for e in events
                        if e.event_type == "REPORT_REJECTED"
                    ],
                    "budget_exhaustion": [
                        e.details for e in events if e.event_type == "BUDGET_EXHAUSTED"
                    ],
                    "termination_code": report.get("termination_code"),
                    "investigation_turns": investigation_turns,
                    "tool_names": tool_names,
                    "attempted_tool_names": [
                        e.details.get("tool") for e in events if e.event_type == "TOOL_STARTED"
                    ],
                    "token_total_known": sum(
                        (c.get("usage") or {}).get("total_tokens") or 0 for c in calls
                    ),
                    "unknown_usage_calls": sum(
                        (c.get("usage") or {}).get("total_tokens") is None for c in calls
                    ),
                    "failure_type": failure,
                    "error_code": error_code,
                    "error_sites": [
                        e.details.get("error_site") for e in events if e.details.get("error_site")
                    ],
                    "checks": checks,
                }
            )
            reports.append({"synthetic": True, "variant": index, "report": report})
            if failure or not checks["financial_records_unchanged"]:
                break
        paired = len(reports) == 2 and all(r["report"] for r in reports)
        # This detects a changed conclusion, not semantic correctness. Human review
        # must assess whether the change follows the amendment-present/absent fact.
        conclusions = [
            {
                k: r["report"].get(k)
                for k in (
                    "summary",
                    "resolution_rationale",
                    "uncertainties",
                    "proposed_action",
                )
            }
            for r in reports
        ]
        changed = paired and conclusions[0] != conclusions[1]
    return {
        "synthetic": True,
        "provider": "gemini",
        "schema_removed": True,
        "pair_attempts": 1,
        "cases": metrics,
        "counterfactual_conclusion_changed": bool(changed),
        "semantic_correctness": "REQUIRES HUMAN REVIEW OF SYNTHETIC REPORTS",
        "passed": bool(changed) and all(all(c["checks"].values()) for c in metrics),
    }, reports


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-paid-synthetic", action="store_true", required=True)
    args = parser.parse_args()
    if not args.run_paid_synthetic:
        raise SystemExit("Explicit paid synthetic flag required")
    values = dotenv_values(ROOT / ".env")
    key = os.getenv("GEMINI_API_KEY") or values.get("GEMINI_API_KEY", "")
    model = os.getenv("GEMINI_MODEL") or values.get("GEMINI_MODEL", "")
    if not key or not model:
        raise SystemExit("Configured Gemini key/model required; values are never printed")
    url = make_url(os.getenv("TEST_DATABASE_URL") or values["DATABASE_URL"])
    if url.host == "postgres":
        url = url.set(host="127.0.0.1", port=5433)
    target = ROOT / "storage/day-13-live-smoke.json"
    try:
        metrics, reports = run_pair(url, key, model)
    except Exception as exc:  # noqa: BLE001 - no keys/provider bodies in CLI failures
        metrics, reports = {"passed": False, "failure_type": type(exc).__name__}, []
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    target.with_name("day-13-live-synthetic-reports.json").write_text(
        json.dumps(reports, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(metrics, indent=2))
    if not metrics["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
