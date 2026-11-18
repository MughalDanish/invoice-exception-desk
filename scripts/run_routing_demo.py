"""Day 7: exercise all four supervisor routes using isolated synthetic schemas."""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db.models import Vendor
from app.qa import checked, detail, isolated_client, process, upload
from dotenv import dotenv_values
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session


def main():
    values = dotenv_values(ROOT / ".env")
    url = make_url(os.getenv("TEST_DATABASE_URL") or values["DATABASE_URL"])
    if url.host == "postgres":
        url = url.set(host="127.0.0.1", port=5433)
    reports = []
    for case in (
        "wrong-total.pdf",
        "duplicate-altered.pdf",
        "unknown-vendor-1.pdf",
        "outlier",
    ):
        with isolated_client(url) as client:
            if case == "duplicate-altered.pdf":
                process(client, upload(client, "clean-001.pdf")["invoice_id"])
            if case == "outlier":
                # Synthetic setup only, inside the disposable schema. No real policy changes.
                with Session(client.app.state.engine) as db:
                    for vendor in db.scalars(select(Vendor)):
                        vendor.baseline_amount_limit = "100.00"
                    db.commit()
            identifier = upload(client, "clean-001.pdf" if case == "outlier" else case)[
                "invoice_id"
            ]
            process(client, identifier)
            before = detail(client, identifier)
            report = checked(
                client.post(
                    f"/api/v1/invoices/{identifier}/investigations",
                    json={
                        "expected_revision": before["revision"],
                        "idempotency_key": "day-7-demo",
                    },
                ),
                (202,),
            )
            if report["status"] != "COMPLETED" or detail(client, identifier) != before:
                raise RuntimeError(
                    "Investigation did not complete without invoice changes"
                )
            if checked(client.get("/api/v1/ledger"))["total"] != 0:
                raise RuntimeError("Unexpected ledger mutation")
            reports.append({"synthetic": True, "case": case, **report})
    output = ROOT / "storage/day-7-synthetic-reports.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(reports, indent=2), encoding="utf-8")
    print(
        "Four mock routes completed; original invoice responses and empty ledgers preserved."
    )
    print(
        "Reports: storage/day-7-synthetic-reports.json; all disposable schemas removed."
    )


if __name__ == "__main__":
    main()
