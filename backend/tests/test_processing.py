import copy
import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from alembic.config import Config
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from alembic import command
from app.db.models import Invoice, InvoiceStatus, LedgerEntry, ProcessingAttempt, ValidationResult
from app.modules.extraction.adapters import ExtractionError, MockExtractor, get_extractor
from app.modules.invoices.states import transition
from app.seed import seed_vendors
from tests.conftest import AUTH, ROOT, operator_auth

pytestmark = pytest.mark.postgres


def upload_fixture(client, name="clean-001.pdf"):
    content = (ROOT / "fixtures/invoices" / name).read_bytes()
    result = client.post(
        "/api/v1/invoices/upload",
        **operator_auth(client),
        files={"file": (name, content, "application/pdf")},
    )
    assert result.status_code in (200, 201)
    return result.json()["invoice_id"]


def process(client, invoice_id, retry=False):
    return client.post(
        f"/api/v1/invoices/{invoice_id}/process", **operator_auth(client), params={"retry": retry}
    )


def detail(client, invoice_id):
    result = client.get(f"/api/v1/invoices/{invoice_id}", **operator_auth(client))
    assert result.status_code == 200
    return result.json()


def seed(engine):
    with Session(engine) as session:
        seed_vendors(session)


def clean_payload():
    return copy.deepcopy(
        json.loads((ROOT / "fixtures/answers.json").read_text())["fixtures"]["clean-001.pdf"][
            "extraction"
        ]
    )


class FixedExtractor:
    def __init__(self, payload=None):
        self.payload = payload or clean_payload()

    def extract(self, file_path, mime_type):
        return self.payload


@pytest.mark.parametrize(
    "fixture,expected_state,expected_rule",
    [
        ("clean-001.pdf", "READY_TO_POST", None),
        ("wrong-total.pdf", "NEEDS_REVIEW", "TOTAL_MISMATCH"),
        ("wrong-line.pdf", "NEEDS_REVIEW", "LINE_TOTAL_MISMATCH"),
        ("wrong-tax.pdf", "NEEDS_REVIEW", "TAX_RATE_MISMATCH"),
        ("unknown-vendor-1.pdf", "NEEDS_REVIEW", "UNAPPROVED_VENDOR"),
        ("missing-invoice_date.pdf", "NEEDS_REVIEW", "MISSING_REQUIRED_FIELD"),
    ],
)
def test_fixture_processing_and_persisted_rules(
    pg_client, pg_engine, fixture, expected_state, expected_rule
):
    seed(pg_engine)
    invoice_id = upload_fixture(pg_client, fixture)
    result = process(pg_client, invoice_id)
    assert result.status_code == 200
    assert result.json()["status"] == expected_state
    with Session(pg_engine) as session:
        assert session.scalar(select(func.count()).select_from(LedgerEntry)) == 0
    invoice = detail(pg_client, invoice_id)
    assert invoice["current_data"] == invoice["extracted_data"]
    assert invoice["review_required"] == (expected_state == "NEEDS_REVIEW")
    assert invoice["processing_attempts"][0]["status"] == "SUCCEEDED"
    if expected_rule:
        rule = next(r for r in invoice["validations"] if r["rule_code"] == expected_rule)
        assert rule["passed"] is False and rule["severity"] == "BLOCKER"
        if expected_rule == "TOTAL_MISMATCH":
            assert rule["expected"] == {"amount": "2300.00"}
            assert rule["observed"] == {"amount": "2500.00"}
    events = pg_client.get(
        f"/api/v1/invoices/{invoice_id}/audit", **operator_auth(pg_client)
    ).json()
    transitions = [event["details"] for event in events if event["event_type"] == "STATE_CHANGED"]
    assert {row["to"] for row in transitions} == {"EXTRACTING", expected_state}


def test_altered_total_and_normalized_business_duplicates(pg_client, pg_engine):
    seed(pg_engine)
    original = upload_fixture(pg_client)
    assert process(pg_client, original).json()["status"] == "READY_TO_POST"
    altered = upload_fixture(pg_client, "duplicate-altered.pdf")
    assert process(pg_client, altered).json()["status"] == "NEEDS_REVIEW"
    assert any(
        r["rule_code"] == "DUPLICATE_INVOICE" and not r["passed"]
        for r in detail(pg_client, altered)["validations"]
    )
    payload = clean_payload()
    payload.update(vendor_name="  ＡLPHA Office SUPPLIES ", invoice_number=" inv-a-001 ")
    pg_client.app.dependency_overrides[get_extractor] = lambda: FixedExtractor(payload)
    other = upload_fixture(pg_client, "clean-002.pdf")
    assert process(pg_client, other).json()["status"] == "NEEDS_REVIEW"
    assert any(
        r["rule_code"] == "DUPLICATE_INVOICE" and not r["passed"]
        for r in detail(pg_client, other)["validations"]
    )


def test_repeated_processing_does_not_overwrite_or_append_results(pg_client, pg_engine):
    seed(pg_engine)
    invoice_id = upload_fixture(pg_client)
    first = process(pg_client, invoice_id)
    before = detail(pg_client, invoice_id)
    second = process(pg_client, invoice_id)
    assert first.json() == second.json()
    assert detail(pg_client, invoice_id) == before
    assert (
        pg_client.get("/api/v1/invoices?search=INV-A-001", **operator_auth(pg_client)).json()[
            "total"
        ]
        == 1
    )
    assert (
        pg_client.get("/api/v1/invoices?search=Alpha", **operator_auth(pg_client)).json()["total"]
        == 1
    )


def test_failure_requires_explicit_retry_and_can_recover(pg_client, pg_engine):
    seed(pg_engine)

    class TimeoutExtractor:
        def extract(self, path, mime_type):
            raise ExtractionError("GEMINI_TIMEOUT")

    pg_client.app.dependency_overrides[get_extractor] = lambda: TimeoutExtractor()
    invoice_id = upload_fixture(pg_client)
    failed = process(pg_client, invoice_id)
    assert failed.json()["status"] == "EXTRACTION_FAILED"
    assert failed.json()["error_code"] == "GEMINI_TIMEOUT"
    assert process(pg_client, invoice_id).status_code == 409
    pg_client.app.dependency_overrides[get_extractor] = lambda: FixedExtractor()
    assert process(pg_client, invoice_id, retry=True).json()["status"] == "READY_TO_POST"
    attempts = detail(pg_client, invoice_id)["processing_attempts"]
    assert [a["status"] for a in attempts] == ["FAILED", "SUCCEEDED"]
    assert [a["ordinal"] for a in attempts] == [1, 2]


def test_unknown_file_and_invalid_output_fail_explicitly(pg_client, pg_engine):
    seed(pg_engine)
    content = (ROOT / "fixtures/invoices/clean-001.pdf").read_bytes() + b"\n% unknown file\n"
    upload = pg_client.post(
        "/api/v1/invoices/upload",
        **operator_auth(pg_client),
        files={"file": ("clean-001.pdf", content, "application/pdf")},
    )
    invoice_id = upload.json()["invoice_id"]
    assert process(pg_client, invoice_id).json()["error_code"] == "MOCK_FIXTURE_NOT_FOUND"
    pg_client.app.dependency_overrides[get_extractor] = lambda: FixedExtractor({"total": True})
    result = process(pg_client, invoice_id, retry=True)
    assert result.json()["error_code"] == "INVALID_EXTRACTION_OUTPUT"
    assert detail(pg_client, invoice_id)["current_data"] is None


def test_error_fixture_and_generic_failure_never_expose_exception_text(pg_client):
    invoice_id = upload_fixture(pg_client, "extraction-failure.pdf")
    assert process(pg_client, invoice_id).json()["error_code"] == "MOCK_EXTRACTION_FAILED"

    class BrokenExtractor:
        def extract(self, path, mime_type):
            raise RuntimeError("private-invoice-text-secret")

    pg_client.app.dependency_overrides[get_extractor] = lambda: BrokenExtractor()
    assert (
        process(pg_client, invoice_id, retry=True).json()["error_code"]
        == "EXTRACTION_INTERNAL_ERROR"
    )
    assert "private-invoice-text-secret" not in json.dumps(detail(pg_client, invoice_id))


def test_missing_original_file_becomes_recoverable_failure(pg_client, pg_engine, settings):
    invoice_id = upload_fixture(pg_client)
    with Session(pg_engine) as session:
        invoice = session.get(Invoice, uuid.UUID(invoice_id))
        (settings.storage_dir / invoice.file_path).unlink()
    assert process(pg_client, invoice_id).json()["error_code"] == "SOURCE_FILE_UNAVAILABLE"


@pytest.mark.parametrize("long_running_gemini", [False, True])
def test_concurrent_processing_is_visible_and_idempotent(
    pg_client, pg_engine, settings, long_running_gemini
):
    if long_running_gemini:
        settings.ai_mode = "gemini"
    seed(pg_engine)
    started, release = threading.Event(), threading.Event()

    class BlockingExtractor:
        def extract(self, path, mime_type):
            started.set()
            assert release.wait(30)
            return clean_payload()

    pg_client.app.dependency_overrides[get_extractor] = lambda: BlockingExtractor()
    invoice_id = upload_fixture(pg_client)
    with ThreadPoolExecutor(max_workers=1) as pool:
        running = pool.submit(process, pg_client, invoice_id)
        try:
            assert started.wait(30)
            if long_running_gemini:
                with Session(pg_engine) as db:
                    attempt = db.scalar(select(ProcessingAttempt))
                    attempt.created_at = datetime.now(UTC) - timedelta(minutes=3)
                    db.commit()
            visible = detail(pg_client, invoice_id)
            assert visible["status"] == "EXTRACTING"
            assert visible["processing_attempts"][0]["status"] == "RUNNING"
            assert process(pg_client, invoice_id, retry=True).json()["status"] == "EXTRACTING"
        finally:
            release.set()
        assert running.result(timeout=30).json()["status"] == "READY_TO_POST"
    with Session(pg_engine) as session:
        assert session.scalar(select(func.count()).select_from(ProcessingAttempt)) == 1
        assert session.scalar(select(func.count()).select_from(ValidationResult)) > 0


def test_concurrent_business_duplicates_cannot_both_be_ready(pg_client, pg_engine):
    seed(pg_engine)
    barrier = threading.Barrier(2, timeout=30)

    class SimultaneousExtractor:
        def extract(self, path, mime_type):
            barrier.wait()
            return MockExtractor(ROOT / "fixtures").extract(path, mime_type)

    pg_client.app.dependency_overrides[get_extractor] = lambda: SimultaneousExtractor()
    ids = [upload_fixture(pg_client), upload_fixture(pg_client, "duplicate-altered.pdf")]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda invoice_id: process(pg_client, invoice_id), ids))
    assert all(result.status_code == 200 for result in results)
    assert sorted(result.json()["status"] for result in results) == [
        "NEEDS_REVIEW",
        "READY_TO_POST",
    ]
    held = next(
        result.json()["invoice_id"]
        for result in results
        if result.json()["status"] == "NEEDS_REVIEW"
    )
    assert any(
        r["rule_code"] == "DUPLICATE_INVOICE" and not r["passed"]
        for r in detail(pg_client, held)["validations"]
    )


def test_stale_worker_cannot_overwrite_newer_attempt(pg_client, pg_engine):
    seed(pg_engine)
    started, release = threading.Event(), threading.Event()

    class BlockingExtractor:
        def extract(self, path, mime_type):
            started.set()
            assert release.wait(30)
            return clean_payload()

    pg_client.app.dependency_overrides[get_extractor] = lambda: BlockingExtractor()
    invoice_id = upload_fixture(pg_client)
    with ThreadPoolExecutor(max_workers=1) as pool:
        old = pool.submit(process, pg_client, invoice_id)
        try:
            assert started.wait(30)
            with Session(pg_engine) as session:
                attempt = session.scalar(select(ProcessingAttempt))
                attempt.created_at = datetime.now(UTC) - timedelta(minutes=3)
                session.commit()
            pg_client.app.dependency_overrides[get_extractor] = lambda: FixedExtractor()
            assert process(pg_client, invoice_id, retry=True).json()["status"] == "READY_TO_POST"
        finally:
            release.set()
        assert old.result(timeout=30).status_code == 409
    attempts = detail(pg_client, invoice_id)["processing_attempts"]
    assert [a["status"] for a in attempts] == ["FAILED", "SUCCEEDED"]
    assert attempts[0]["error_code"] == "PROCESSING_INTERRUPTED"


@pytest.mark.parametrize("state", [InvoiceStatus.POSTED, InvoiceStatus.REJECTED])
def test_terminal_invoices_cannot_be_reextracted(pg_client, pg_engine, state):
    invoice_id = upload_fixture(pg_client)
    with Session(pg_engine) as session:
        session.get(Invoice, uuid.UUID(invoice_id)).status = state
        session.commit()
    assert process(pg_client, invoice_id).status_code == 409


def test_process_auth_and_unknown_id(pg_client):
    assert pg_client.post(f"/api/v1/invoices/{uuid.uuid4()}/process").status_code == 401
    assert process(pg_client, str(uuid.uuid4())).status_code == 404


def test_day2_migration_preserves_day1_invoice(pg_client, pg_engine):
    invoice_id = upload_fixture(pg_client)
    with pg_engine.begin() as connection:
        config = Config(str(ROOT / "backend/alembic.ini"))
        config.attributes["connection"] = connection
        command.downgrade(config, "0001_foundation")
        assert connection.scalar(text("SELECT count(*) FROM invoices")) == 1
    assert pg_client.get("/health").status_code == 503
    with pg_engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    assert pg_client.get("/health").status_code == 200
    # Downgrading before auth was introduced removes accounts and sessions too.
    from app.modules.auth.bootstrap import bootstrap_operator

    with Session(pg_engine) as db:
        bootstrap_operator(db, *AUTH)
    nonce = pg_client.get("/api/v1/auth/csrf").json()["csrf_token"]
    signed = pg_client.post(
        "/api/v1/auth/login",
        json={"username": AUTH[0], "password": AUTH[1]},
        headers={"X-CSRF-Token": nonce},
    )
    assert signed.status_code == 200
    pg_client.operator_cookies = dict(pg_client.cookies)
    pg_client.headers["X-CSRF-Token"] = signed.json()["csrf_token"]
    invoice = detail(pg_client, invoice_id)
    assert invoice["status"] == "RECEIVED" and invoice["review_required"] is False


def test_invalid_state_transition_has_no_audit_event(pg_engine):
    from app.core.errors import AppError
    from app.db.models import AuditEvent

    with Session(pg_engine) as session:
        invoice = Invoice(id=uuid.uuid4(), status=InvoiceStatus.RECEIVED)
        with pytest.raises(AppError, match="requested state"):
            transition(session, invoice, InvoiceStatus.POSTED, "operator")
        assert session.scalar(select(func.count()).select_from(AuditEvent)) == 0
