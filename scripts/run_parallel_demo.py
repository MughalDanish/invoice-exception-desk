"""Day 8 mock demo: explicitly seed synthetic evidence ONLY in a disposable schema."""

import json
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db.models import InvestigationDocument, Invoice
from app.modules.approvals.service import payload_hash
from app.qa import (
    checked,
    complete_synthetic_investigation,
    detail,
    isolated_client,
    process,
    upload,
)
from dotenv import dotenv_values
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session


def main():
    values = dotenv_values(ROOT / ".env")
    url = make_url(os.getenv("TEST_DATABASE_URL") or values["DATABASE_URL"])
    if url.host == "postgres":
        url = url.set(host="127.0.0.1", port=5433)
    corpus = json.loads((ROOT / "fixtures/investigation/day-8-corpus.json").read_text())
    assert corpus["synthetic"] is True
    reports = []
    with isolated_client(url) as client:
        identifier = upload(client, "wrong-total.pdf")["invoice_id"]
        process(client, identifier)
        before = detail(client, identifier)

        def investigate(key):
            result = checked(
                client.post(
                    f"/api/v1/invoices/{identifier}/investigations",
                    json={
                        "expected_revision": before["revision"],
                        "idempotency_key": key,
                    },
                ),
                (202,),
            )
            result = complete_synthetic_investigation(client, result)
            assert result["status"] == "COMPLETED", "Mock investigation failed"
            assert detail(client, identifier) == before, "Financial records changed"
            assert checked(client.get("/api/v1/ledger"))["total"] == 0
            reports.append(result)
            return result

        first = investigate("day-8-missing")
        with Session(client.app.state.engine) as db:
            invoice = db.get(Invoice, uuid.UUID(identifier))
            for source in corpus["sources"]:
                db.add(
                    InvestigationDocument(
                        source_id=uuid.UUID(source["source_id"]),
                        version=source["version"],
                        invoice_id=invoice.id,
                        supplier_key=invoice.normalized_vendor_name,
                        kind=source["kind"],
                        content=source["text"],
                        content_sha256=payload_hash({"text": source["text"]}),
                    )
                )
            db.commit()
        assert (
            checked(client.get(f"/api/v1/investigations/{first['run_id']}"))["status"]
            == "STALE"
        )
        investigate("day-8-supported-inventory")
    target = ROOT / "storage/day-8-synthetic-reports.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(reports, indent=2), encoding="utf-8")
    print(
        "Missing/populated evidence demos passed; prior report stale; invoice/ledger unchanged."
    )
    print("Synthetic schema removed. Reports: storage/day-8-synthetic-reports.json")


if __name__ == "__main__":
    main()
