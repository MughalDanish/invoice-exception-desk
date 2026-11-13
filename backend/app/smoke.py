"""Repeatable Day 3 API demo: synthetic review, posting, audit and CSV, without secrets."""

import csv
import io
import json

import httpx

from app.core.config import Settings


def main():
    settings = Settings()
    if settings.ai_mode != "mock":
        raise SystemExit("The repeatable smoke demo requires AI_MODE=mock")
    auth = (settings.demo_basic_user, settings.demo_basic_password.get_secret_value())
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=30) as client:
        health = client.get("/health")
        health.raise_for_status()
        assert client.get("/api/v1/invoices").status_code == 401

        def get_invoice(invoice_id):
            response = client.get(f"/api/v1/invoices/{invoice_id}", auth=auth)
            response.raise_for_status()
            return response.json()

        def ingest(name):
            content = (settings.fixtures_dir / "invoices" / name).read_bytes()
            response = client.post(
                "/api/v1/invoices/upload",
                auth=auth,
                files={"file": (name, content, "application/pdf")},
            )
            response.raise_for_status()
            invoice_id = response.json()["invoice_id"]
            invoice = get_invoice(invoice_id)
            if invoice["status"] in ("RECEIVED", "EXTRACTION_FAILED"):
                processed = client.post(
                    f"/api/v1/invoices/{invoice_id}/process",
                    auth=auth,
                    params={"retry": invoice["status"] == "EXTRACTION_FAILED"},
                )
                processed.raise_for_status()
            return invoice_id

        def act(invoice_id, name, **fields):
            invoice = get_invoice(invoice_id)
            return client.post(
                f"/api/v1/invoices/{invoice_id}/{name}",
                auth=auth,
                json={"expected_revision": invoice["revision"], **fields},
            )

        def eligible(invoice_id):
            invoice = get_invoice(invoice_id)
            if invoice["status"] == "POSTED":
                return
            validated = act(invoice_id, "revalidate")
            validated.raise_for_status()
            if validated.json()["status"] == "NEEDS_REVIEW":
                reviewed = act(
                    invoice_id,
                    "review",
                    decision="APPROVE",
                    notes="Verified synthetic invoice fields and arithmetic",
                )
                reviewed.raise_for_status()

        clean = ingest("clean-001.pdf")
        duplicate = ingest("duplicate-altered.pdf")
        if get_invoice(duplicate)["status"] != "REJECTED":
            assert act(duplicate, "review", decision="APPROVE").status_code == 409
            assert act(duplicate, "post").status_code == 409
            rejected = act(
                duplicate, "review", decision="REJECT", notes="Duplicate synthetic supplier invoice"
            )
            rejected.raise_for_status()
        assert act(duplicate, "post").status_code == 409
        eligible(clean)
        clean_post = act(clean, "post")
        clean_post.raise_for_status()
        assert clean_post.json()["total"] == "1150.00"
        assert act(clean, "post").json()["id"] == clean_post.json()["id"]

        wrong = ingest("wrong-total.pdf")
        current = get_invoice(wrong)
        if current["status"] != "POSTED":
            if current["current_data"]["total"] == "2500.00":
                assert act(wrong, "post").status_code == 409
                assert act(wrong, "review", decision="APPROVE").status_code == 409
                changed = client.patch(
                    f"/api/v1/invoices/{wrong}",
                    auth=auth,
                    json={
                        "expected_revision": current["revision"],
                        "changes": {"total": "2300.00"},
                        "notes": "Corrected grand total: subtotal 2000.00 plus tax 300.00",
                    },
                )
                changed.raise_for_status()
                assert act(wrong, "post").status_code == 409
            eligible(wrong)
        corrected_post = act(wrong, "post")
        corrected_post.raise_for_status()
        assert corrected_post.json()["total"] == "2300.00"
        assert act(wrong, "post").json()["id"] == corrected_post.json()["id"]
        original = client.get(f"/api/v1/invoices/{clean}/file", auth=auth)
        original.raise_for_status()
        assert original.content == (settings.fixtures_dir / "invoices/clean-001.pdf").read_bytes()
        exported = client.get("/api/v1/ledger/export.csv", auth=auth)
        exported.raise_for_status()
        rows = list(csv.DictReader(io.StringIO(exported.content.decode("utf-8-sig"), newline="")))
        by_invoice = {row["invoice_id"]: row for row in rows}
        assert clean in by_invoice and wrong in by_invoice and duplicate not in by_invoice
        assert by_invoice[wrong]["total"] == "2300.00"
        audits = client.get(f"/api/v1/invoices/{wrong}/audit", auth=auth)
        audits.raise_for_status()
        assert any(
            event["event_type"] == "INVOICE_CORRECTED"
            and event["details"]["diff"].get("total") == {"before": "2500.00", "after": "2300.00"}
            for event in audits.json()
        )
        assert get_invoice(clean)["status"] == get_invoice(wrong)["status"] == "POSTED"
        assert get_invoice(duplicate)["status"] == "REJECTED"
        print(
            json.dumps(
                {
                    "health": health.json(),
                    "clean_ledger_id": clean_post.json()["id"],
                    "corrected_ledger_id": corrected_post.json()["id"],
                    "corrected_revision": corrected_post.json()["invoice_revision"],
                    "duplicate_status": "REJECTED",
                    "duplicate_post": "blocked",
                    "repeat_post": "same ledger IDs",
                    "csv_rows": len(rows),
                    "correction_audit": "2500.00 to 2300.00 verified",
                    "source_download": "matches bytes",
                    "unauthenticated_access": "blocked",
                }
            )
        )


if __name__ == "__main__":
    main()
