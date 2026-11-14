import concurrent.futures

import pytest
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import IntegrationDelivery, Invoice, LedgerEntry
from tests.conftest import AUTH, ROOT, operator_auth
from tests.test_processing import seed

KEY = "integration-test-secret-only"
PATH = "/api/v1/integrations/n8n/invoices"


def send(client, filename="clean-001.pdf", delivery="message-1:attachment-0", key=KEY):
    return client.post(
        PATH,
        headers={"X-Integration-Key": key, "Idempotency-Key": delivery},
        files={
            "file": (
                filename,
                (ROOT / "fixtures/invoices" / filename).read_bytes(),
                "application/pdf",
            )
        },
    )


def test_integration_rejects_missing_wrong_and_operator_credentials(client, settings, clean_pdf):
    settings.n8n_integration_key = SecretStr(KEY)
    for headers, auth in [({}, None), ({"X-Integration-Key": "wrong"}, None), ({}, AUTH)]:
        response = client.post(
            PATH,
            headers=headers,
            auth=auth,
            files={"file": ("invoice.pdf", clean_pdf, "application/pdf")},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "INTEGRATION_UNAUTHORIZED"
    assert client.get("/api/v1/invoices", headers={"X-Integration-Key": KEY}).status_code == 401
    settings.n8n_integration_key = SecretStr("")
    assert send(client).status_code == 403


@pytest.mark.postgres
def test_receipt_replay_conflict_and_cross_source_dedup(pg_client, pg_engine, settings):
    settings.n8n_integration_key = SecretStr(KEY)
    seed(pg_engine)
    first = send(pg_client)
    assert first.status_code == 201
    assert first.json()["status"] == "READY_TO_POST"
    invoice_id = first.json()["invoice_id"]
    again = send(pg_client)
    assert again.status_code == 200
    assert again.json()["invoice_id"] == invoice_id
    conflict = send(pg_client, "clean-002.pdf")
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    assert send(pg_client, delivery="another-message:0").json()["invoice_id"] == invoice_id
    # Receipt creation also works if the same bytes originally came from the dashboard.
    raw = (ROOT / "fixtures/invoices/clean-002.pdf").read_bytes()
    direct = pg_client.post(
        "/api/v1/invoices/upload",
        **operator_auth(pg_client),
        files={"file": ("other.pdf", raw, "application/pdf")},
    ).json()
    cross = send(pg_client, "clean-002.pdf", "cross-source:0")
    assert cross.json()["invoice_id"] == direct["invoice_id"]
    with Session(pg_engine) as session:
        assert session.scalar(select(func.count()).select_from(Invoice)) == 2
        assert session.scalar(select(func.count()).select_from(IntegrationDelivery)) == 3
        assert session.scalar(select(func.count()).select_from(LedgerEntry)) == 0
    audit = pg_client.get(f"/api/v1/invoices/{invoice_id}/audit", **operator_auth(pg_client)).json()
    assert any(e["actor"] == "integration:n8n" for e in audit)
    assert KEY not in str(audit)


@pytest.mark.postgres
def test_concurrent_delivery_one_receipt_one_invoice(pg_client, pg_engine, settings):
    settings.n8n_integration_key = SecretStr(KEY)
    seed(pg_engine)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(lambda _: send(pg_client), range(4)))
    assert all(r.status_code in (200, 201, 202) for r in responses)
    assert len({r.json()["invoice_id"] for r in responses}) == 1
    with Session(pg_engine) as session:
        assert session.scalar(select(func.count()).select_from(IntegrationDelivery)) == 1
        assert session.scalar(select(func.count()).select_from(Invoice)) == 1


@pytest.mark.postgres
def test_exception_result_filters_and_stats(pg_client, pg_engine, settings):
    settings.n8n_integration_key = SecretStr(KEY)
    seed(pg_engine)
    response = send(pg_client, "wrong-total.pdf")
    assert response.status_code == 201
    assert response.json()["status"] == "NEEDS_REVIEW"
    assert "TOTAL_MISMATCH" in response.json()["blocker_codes"]
    rows = pg_client.get(
        "/api/v1/invoices?issue=TOTAL_MISMATCH&status=NEEDS_REVIEW", **operator_auth(pg_client)
    ).json()
    assert rows["total"] == 1
    assert "TOTAL_MISMATCH" in rows["items"][0]["issue_codes"]
    assert rows["items"][0]["current_data"]["total"] == "2500.00"
    stats = pg_client.get("/api/v1/stats", **operator_auth(pg_client)).json()
    assert stats["by_status"]["NEEDS_REVIEW"] == 1
    assert stats["recent_activity"]
    assert "details" not in stats["recent_activity"][0]
    assert (
        pg_client.get("/api/v1/invoices?issue=NOT_A_REAL_RULE", **operator_auth(pg_client)).json()[
            "total"
        ]
        == 0
    )


@pytest.mark.postgres
def test_invalid_keys_files_and_no_automatic_failed_retry(pg_client, settings):
    settings.n8n_integration_key = SecretStr(KEY)
    assert send(pg_client, delivery="unsafe key").status_code == 422
    assert send(pg_client, delivery="").status_code == 422
    invalid = pg_client.post(
        PATH,
        headers={"X-Integration-Key": KEY, "Idempotency-Key": "bad-file"},
        files={"file": ("bad.pdf", b"not pdf", "application/pdf")},
    )
    assert invalid.status_code == 415
    failure_name = next(p.name for p in (ROOT / "fixtures/invoices").glob("*failure*.pdf"))
    first = send(pg_client, failure_name, "fail-1").json()
    assert first["status"] == "EXTRACTION_FAILED"
    again = send(pg_client, failure_name, "fail-1").json()
    assert again["status"] == "EXTRACTION_FAILED"
    detail = pg_client.get(
        f"/api/v1/invoices/{first['invoice_id']}", **operator_auth(pg_client)
    ).json()
    assert len(detail["processing_attempts"]) == 1


@pytest.mark.postgres
def test_notification_detail_is_scoped_read_only_and_exact(pg_client, settings):
    settings.n8n_integration_key = SecretStr(KEY)
    created = send(pg_client, "wrong-total.pdf").json()
    path = f"/api/v1/integrations/n8n/invoices/{created['invoice_id']}"
    assert pg_client.get(path).status_code == 403
    assert pg_client.get(path, **operator_auth(pg_client)).status_code == 403
    result = pg_client.get(path, headers={"X-Integration-Key": KEY})
    assert result.status_code == 200
    data = result.json()
    assert data["total"] == "2500.00" and data["source"] == "gmail"
    assert data["supplier_name"] and data["invoice_number"]
    assert any(r["rule_code"] == "TOTAL_MISMATCH" and not r["passed"] for r in data["validations"])
    assert "extracted_data" not in data and "reviews" not in data
    assert pg_client.post(path, headers={"X-Integration-Key": KEY}).status_code == 405
    assert pg_client.get(path, headers={"X-Integration-Key": KEY}).json() == data


def test_notification_difference_uses_recorded_exact_amounts():
    from types import SimpleNamespace

    from app.db.models import Severity
    from app.modules.invoices.integration import notification_rule

    rule = SimpleNamespace(
        rule_code="TOTAL_MISMATCH",
        severity=Severity.BLOCKER,
        passed=False,
        message="Total check",
        expected={"amount": "9999999999999999.990000"},
        observed={"amount": "10000000000000299.990000"},
    )
    result = notification_rule(rule)
    assert result["difference_amount"] == "300.000000"
    assert result["expected_amount"] == "9999999999999999.990000"
    assert rule.observed["amount"] == "10000000000000299.990000"
    rule.expected = None
    assert "difference_amount" not in notification_rule(rule)
    rule.expected = {"amount": "private-invalid-number"}
    assert "difference_amount" not in notification_rule(rule)
