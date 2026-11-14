"""Isolated PostgreSQL fixture benchmark and curated public read-model export.

Never operates on application tables: every run creates and drops a random schema.
Only the original bundled fixtures and mock extraction provider are used.
"""

import argparse
import csv
import json
import math
import os
import tempfile
import time
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from alembic import command
from app.core.config import Settings
from app.main import create_app
from app.seed import seed_vendors

ROOT = Path(__file__).resolve().parents[2]
AUTH = ("synthetic-operator", "qa-only-not-a-real-credential")


@contextmanager
def isolated_client(url):
    schema = "ied_qa_" + uuid.uuid4().hex
    admin = create_engine(url, connect_args={"connect_timeout": 5})
    engine = create_engine(
        url, connect_args={"connect_timeout": 5, "options": f"-csearch_path={schema}"}
    )
    try:
        with admin.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        with engine.begin() as conn:
            config = Config(str(ROOT / "backend/alembic.ini"))
            config.attributes["connection"] = conn
            command.upgrade(config, "head")
        with tempfile.TemporaryDirectory(prefix="ied-qa-") as folder:
            settings = Settings(
                _env_file=None,
                demo_basic_user=AUTH[0],
                demo_basic_password=AUTH[1],
                ai_mode="mock",
                gemini_api_key="",
                gemini_model="",
                public_demo=False,
                storage_dir=Path(folder),
                fixtures_dir=ROOT / "fixtures",
            )
            with Session(engine) as session:
                seed_vendors(session)
            with TestClient(create_app(settings, engine)) as client:
                yield client
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin.dispose()


def checked(response, codes=(200,)):
    if response.status_code not in codes:
        raise RuntimeError(f"QA request failed: HTTP {response.status_code}")
    return response.json()


def upload(client, name):
    return checked(
        client.post(
            "/api/v1/invoices/upload",
            auth=AUTH,
            files={
                "file": (name, (ROOT / "fixtures/invoices" / name).read_bytes(), "application/pdf")
            },
        ),
        (200, 201),
    )


def process(client, invoice_id):
    return checked(client.post(f"/api/v1/invoices/{invoice_id}/process", auth=AUTH))


def detail(client, invoice_id):
    return checked(client.get(f"/api/v1/invoices/{invoice_id}", auth=AUTH))


def post(client, invoice_id, revision=1):
    return client.post(
        f"/api/v1/invoices/{invoice_id}/post", auth=AUTH, json={"expected_revision": revision}
    )


def percentile(samples, fraction):
    return sorted(samples)[max(0, math.ceil(len(samples) * fraction) - 1)]


def benchmark(url):
    labels = json.loads((ROOT / "fixtures/answers.json").read_text())["fixtures"]
    rows = []
    for name, label in labels.items():
        with isolated_client(url) as client:
            reference_id = None
            if name.startswith("duplicate-"):
                reference_id = upload(client, "clean-001.pdf")["invoice_id"]
                process(client, reference_id)
                checked(post(client, reference_id))
            before = checked(client.get("/api/v1/ledger", auth=AUTH))["total"]
            start = time.perf_counter()
            result = upload(client, name)
            invoice_id = result["invoice_id"]
            if not result["duplicate"]:
                process(client, invoice_id)
            record = detail(client, invoice_id)
            failed = sorted(
                r["rule_code"]
                for r in record["validations"]
                if not r["passed"] and r["severity"] == "BLOCKER"
            )
            attempt = post(client, invoice_id)
            after = checked(client.get("/api/v1/ledger", auth=AUTH))["total"]
            elapsed = round((time.perf_counter() - start) * 1000, 3)
            expected_hold = not name.startswith("clean-")
            prevented = after == before
            error = (
                record["processing_attempts"][-1]["error_code"]
                if record["processing_attempts"]
                else None
            )
            expected_rules = set(label["expected_rule_codes"])
            # Exact duplicate is an ingestion result, not a separate rule batch.
            rules_ok = (
                record["status"] == "EXTRACTION_FAILED"
                if label["error_code"]
                else (
                    (result["duplicate"] and invoice_id == reference_id)
                    if name == "duplicate-copy.pdf"
                    else expected_rules.issubset(failed)
                )
            )
            rows.append(
                {
                    "fixture": name,
                    "sha256": label["sha256"],
                    "status_before_post": record["status"],
                    "expected_hold": expected_hold,
                    "prevented_new_ledger_entry": prevented,
                    "duplicate_file": result["duplicate"],
                    "rule_codes": failed,
                    "post_http": attempt.status_code,
                    "error_code": error,
                    "expected_rules_present": rules_ok,
                    "expected_error_matches": error == label["error_code"],
                    "mock_adapter_matches_answer_key": record["extracted_data"]
                    == label["extraction"],
                    "latency_ms": elapsed,
                }
            )
    tp = sum(r["expected_hold"] and r["prevented_new_ledger_entry"] for r in rows)
    fp = sum(not r["expected_hold"] and r["prevented_new_ledger_entry"] for r in rows)
    fn = sum(r["expected_hold"] and not r["prevented_new_ledger_entry"] for r in rows)
    tn = sum(not r["expected_hold"] and not r["prevented_new_ledger_entry"] for r in rows)
    times = [r["latency_ms"] for r in rows]
    validation_rows = [r for r in rows if not r["duplicate_file"] and r["error_code"] is None]
    return {
        "dataset": "phase-1-original-16-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "provider": "mock",
        "live_model_quality": "NOT RUN",
        "field_extraction_accuracy": "NOT RUN: scripted replay is not independent extraction",
        "latency_scope": (
            "upload + processing + detail + posting attempt + ledger read; "
            "excludes schema setup/reference seeding"
        ),
        "case_count": len(rows),
        "distinct_file_hashes": len({r["sha256"] for r in rows}),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "rule_validation": {
            "case_count": len(validation_rows),
            "tp": sum(r["expected_hold"] and bool(r["rule_codes"]) for r in validation_rows),
            "fp": sum(not r["expected_hold"] and bool(r["rule_codes"]) for r in validation_rows),
            "fn": sum(r["expected_hold"] and not r["rule_codes"] for r in validation_rows),
            "tn": sum(not r["expected_hold"] and not r["rule_codes"] for r in validation_rows),
        },
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "p50_ms": percentile(times, 0.5),
        "p95_ms": percentile(times, 0.95),
        "all_contracts_passed": all(
            r["expected_rules_present"]
            and r["expected_error_matches"]
            and r["mock_adapter_matches_answer_key"]
            and r["expected_hold"] == r["prevented_new_ledger_entry"]
            for r in rows
        ),
        "cases": rows,
    }


def public_export(url):
    with isolated_client(url) as client:
        labels = json.loads((ROOT / "fixtures/answers.json").read_text())["fixtures"]
        ids = []
        for name in labels:
            uploaded = upload(client, name)
            if uploaded["duplicate"]:
                continue
            invoice_id = uploaded["invoice_id"]
            process(client, invoice_id)
            if name == "clean-001.pdf":
                checked(post(client, invoice_id))
            ids.append(invoice_id)
        invoices = [detail(client, value) for value in ids]
        for invoice in invoices:
            invoice["issue_codes"] = sorted(
                r["rule_code"] for r in invoice["validations"] if not r["passed"]
            )
        return {
            "version": 1,
            "synthetic": True,
            "provenance": (
                "isolated PostgreSQL, original fixtures, mock extraction; explicit clean-001 post"
            ),
            "invoices": invoices,
            "audits": {
                value: checked(client.get(f"/api/v1/invoices/{value}/audit", auth=AUTH))
                for value in ids
            },
            "vendors": checked(client.get("/api/v1/vendors", auth=AUTH)),
            "ledger": checked(client.get("/api/v1/ledger", auth=AUTH))["items"],
            "stats": checked(client.get("/api/v1/stats", auth=AUTH)),
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=["benchmark", "public-export"])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    url = os.environ.get("TEST_DATABASE_URL") or Settings().database_url
    data = benchmark(url) if args.kind == "benchmark" else public_export(url)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    if args.kind == "benchmark":
        with args.output.with_suffix(".csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(data["cases"][0]))
            writer.writeheader()
            writer.writerows(data["cases"])
        print(json.dumps({k: v for k, v in data.items() if k != "cases"}))
        if not data["all_contracts_passed"]:
            raise SystemExit(1)
    else:
        print(f"Exported {len(data['invoices'])} synthetic invoices. No application data was read.")


if __name__ == "__main__":
    main()
