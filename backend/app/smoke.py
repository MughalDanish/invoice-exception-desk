"""Exercise running ingestion and Day 2 validation with synthetic PDFs only."""

import json

import httpx

from app.core.config import Settings


def main():
    settings = Settings()
    if settings.ai_mode != "mock":
        raise SystemExit("The repeatable smoke demo requires AI_MODE=mock")
    content = (settings.fixtures_dir / "invoices" / "clean-001.pdf").read_bytes()
    auth = (settings.demo_basic_user, settings.demo_basic_password.get_secret_value())
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=15) as client:
        health = client.get("/health")
        health.raise_for_status()
        assert client.get("/api/v1/invoices").status_code == 401
        first = client.post(
            "/api/v1/invoices/upload",
            auth=auth,
            files={"file": ("clean-001.pdf", content, "application/pdf")},
        )
        first.raise_for_status()
        invoice_id = first.json()["invoice_id"]
        repeated = client.post(
            "/api/v1/invoices/upload",
            auth=auth,
            files={"file": ("clean-001.pdf", content, "application/pdf")},
        )
        assert repeated.status_code == 200
        assert repeated.json()["invoice_id"] == invoice_id
        original = client.get(f"/api/v1/invoices/{invoice_id}/file", auth=auth)
        original.raise_for_status()
        assert original.content == content
        cases = []
        for filename, expected_state, required_rule in (
            ("clean-001.pdf", "READY_TO_POST", None),
            ("wrong-total.pdf", "NEEDS_REVIEW", "TOTAL_MISMATCH"),
            ("duplicate-altered.pdf", "NEEDS_REVIEW", "DUPLICATE_INVOICE"),
        ):
            document = (settings.fixtures_dir / "invoices" / filename).read_bytes()
            ingested = client.post(
                "/api/v1/invoices/upload",
                auth=auth,
                files={"file": (filename, document, "application/pdf")},
            )
            ingested.raise_for_status()
            case_id = ingested.json()["invoice_id"]
            processed = client.post(f"/api/v1/invoices/{case_id}/process", auth=auth)
            processed.raise_for_status()
            assert processed.json()["status"] == expected_state
            details = client.get(f"/api/v1/invoices/{case_id}", auth=auth)
            details.raise_for_status()
            blockers = [
                rule["rule_code"]
                for rule in details.json()["validations"]
                if not rule["passed"] and rule["severity"] == "BLOCKER"
            ]
            if required_rule:
                assert required_rule in blockers
            cases.append({"fixture": filename, "status": expected_state, "blocker_codes": blockers})
        audit = client.get(f"/api/v1/invoices/{invoice_id}/audit", auth=auth)
        audit.raise_for_status()
        print(
            json.dumps(
                {
                    "health": health.json(),
                    "invoice_id": invoice_id,
                    "upload_status": first.json()["status"],
                    "repeat_upload": "same invoice ID",
                    "original_download": "matches source bytes",
                    "audit_events": len(audit.json()),
                    "unauthenticated_access": "blocked",
                    "validation_cases": cases,
                }
            )
        )


if __name__ == "__main__":
    main()
