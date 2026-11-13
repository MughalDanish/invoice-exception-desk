"""Exercise the running local API with one synthetic PDF; never print credentials."""

import json

import httpx

from app.core.config import Settings


def main():
    settings = Settings()
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
        audit = client.get(f"/api/v1/invoices/{invoice_id}/audit", auth=auth)
        audit.raise_for_status()
        print(
            json.dumps(
                {
                    "health": health.json(),
                    "invoice_id": invoice_id,
                    "status": first.json()["status"],
                    "repeat_upload": "same invoice ID",
                    "original_download": "matches source bytes",
                    "audit_events": len(audit.json()),
                    "unauthenticated_access": "blocked",
                }
            )
        )


if __name__ == "__main__":
    main()
