"""Run the Day 6 mock slice in an isolated synthetic schema; never alter demo data."""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

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


def main():
    values = dotenv_values(ROOT / ".env")
    url = make_url(os.getenv("TEST_DATABASE_URL") or values["DATABASE_URL"])
    if url.host == "postgres":
        url = url.set(host="127.0.0.1", port=5433)
    with isolated_client(url) as client:
        identifier = upload(client, "wrong-total.pdf")["invoice_id"]
        process(client, identifier)
        before = detail(client, identifier)
        report = checked(
            client.post(
                f"/api/v1/invoices/{identifier}/investigations",
                json={
                    "expected_revision": before["revision"],
                    "idempotency_key": "synthetic-day-6",
                },
            ),
            (202,),
        )
        report = complete_synthetic_investigation(client, report)
        if report["status"] != "COMPLETED" or detail(client, identifier) != before:
            raise RuntimeError("Investigation did not complete safely")
        if checked(client.get("/api/v1/ledger"))["total"] != 0:
            raise RuntimeError("Investigation changed ledger")
        output = ROOT / "storage/day-6-synthetic-report.json"
        output.parent.mkdir(exist_ok=True)
        output.write_text(
            json.dumps({"synthetic": True, **report}, indent=2), encoding="utf-8"
        )
    print("Synthetic mock investigation completed; no financial records changed.")
    print("Report: storage/day-6-synthetic-report.json; isolated schema removed.")


if __name__ == "__main__":
    main()
