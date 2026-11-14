import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import Session

from app.db.models import (
    AuditEvent,
    Invoice,
    InvoiceReview,
    LedgerEntry,
    ValidationResult,
    Vendor,
)
from app.modules.approvals.schemas import RevisionRequest
from app.modules.extraction.adapters import parse_extraction
from app.modules.ledger.service import post_invoice
from tests.conftest import AUTH, operator_auth
from tests.test_processing import (
    detail,
    process,
    seed,
    upload_fixture,
)

pytestmark = pytest.mark.postgres


def action(client, invoice_id, name, revision=1, **fields):
    return client.post(
        f"/api/v1/invoices/{invoice_id}/{name}",
        **operator_auth(client),
        json={"expected_revision": revision, **fields},
    )


def correction(client, invoice_id, revision=1, **changes):
    return client.patch(
        f"/api/v1/invoices/{invoice_id}",
        **operator_auth(client),
        json={
            "expected_revision": revision,
            "changes": changes,
            "notes": "Checked against the synthetic source",
        },
    )


def prepared(client, engine, filename="clean-001.pdf"):
    seed(engine)
    invoice_id = upload_fixture(client, filename)
    assert process(client, invoice_id).status_code == 200
    return invoice_id


def test_clean_post_is_idempotent_and_audited(pg_client, pg_engine):
    invoice_id = prepared(pg_client, pg_engine)
    first = action(pg_client, invoice_id, "post")
    assert first.status_code == 200
    assert first.json()["total"] == "1150.00"
    assert first.json()["invoice_number"] == "INV-A-001"
    assert first.json()["posted_by"] == AUTH[0]
    assert action(pg_client, invoice_id, "post").json() == first.json()
    assert detail(pg_client, invoice_id)["status"] == "POSTED"
    assert detail(pg_client, invoice_id)["ledger_entry_id"] == first.json()["id"]
    with Session(pg_engine) as session:
        assert session.scalar(select(func.count()).select_from(LedgerEntry)) == 1
        events = session.scalars(
            select(AuditEvent).where(AuditEvent.event_type == "LEDGER_POSTED")
        ).all()
        assert len(events) == 1
    assert action(pg_client, invoice_id, "post", revision=2).status_code == 409


def test_wrong_total_requires_correction_revalidation_and_current_review(pg_client, pg_engine):
    invoice_id = prepared(pg_client, pg_engine, "wrong-total.pdf")
    assert action(pg_client, invoice_id, "review", decision="APPROVE").status_code == 409
    assert action(pg_client, invoice_id, "post").status_code == 409
    changed = correction(pg_client, invoice_id, total="2300.00")
    assert changed.status_code == 200 and changed.json()["revision"] == 2
    edited = detail(pg_client, invoice_id)
    assert edited["extracted_data"]["total"] == "2500.00"
    assert edited["current_data"]["total"] == "2300.00"
    assert edited["validations"] == [] and edited["validated_revision"] is None
    assert (
        action(pg_client, invoice_id, "review", revision=2, decision="APPROVE").json()["error"][
            "code"
        ]
        == "REVALIDATION_REQUIRED"
    )
    assert action(pg_client, invoice_id, "post", revision=2).status_code == 409
    validated = action(pg_client, invoice_id, "revalidate", revision=2)
    assert validated.json()["status"] == "NEEDS_REVIEW"
    assert (
        action(pg_client, invoice_id, "post", revision=2).json()["error"]["code"]
        == "APPROVAL_REQUIRED"
    )
    approved = action(
        pg_client,
        invoice_id,
        "review",
        revision=2,
        decision="APPROVE",
        notes="Subtotal plus tax verified",
    )
    assert approved.status_code == 200 and approved.json()["status"] == "READY_TO_POST"
    posted = action(pg_client, invoice_id, "post", revision=2)
    assert posted.status_code == 200 and posted.json()["total"] == "2300.00"
    assert posted.json()["invoice_revision"] == 2
    with Session(pg_engine) as session:
        event = session.scalar(
            select(AuditEvent).where(AuditEvent.event_type == "INVOICE_CORRECTED")
        )
        assert event.details["diff"]["total"] == {"before": "2500.00", "after": "2300.00"}
        review = session.scalar(select(InvoiceReview))
        assert (
            review.reviewer == AUTH[0] and review.revision == 2 and len(review.payload_sha256) == 64
        )


def test_new_correction_invalidates_prior_approval_and_stale_requests(pg_client, pg_engine):
    invoice_id = prepared(pg_client, pg_engine)
    assert action(pg_client, invoice_id, "review", decision="APPROVE").status_code == 200
    assert correction(pg_client, invoice_id, due_date="2026-12-01").json()["revision"] == 2
    assert correction(pg_client, invoice_id, invoice_number="STALE").status_code == 409
    for name in ("post", "revalidate"):
        assert action(pg_client, invoice_id, name).status_code == 409
    assert action(pg_client, invoice_id, "review", decision="APPROVE").status_code == 409
    assert (
        action(pg_client, invoice_id, "review", decision="REJECT", notes="Stale action").status_code
        == 409
    )
    assert (
        action(pg_client, invoice_id, "revalidate", revision=2).json()["status"] == "NEEDS_REVIEW"
    )
    assert (
        action(pg_client, invoice_id, "post", revision=2).json()["error"]["code"]
        == "APPROVAL_REQUIRED"
    )
    assert (
        action(pg_client, invoice_id, "review", revision=2, decision="APPROVE").status_code == 200
    )
    assert action(pg_client, invoice_id, "post", revision=2).status_code == 200


def test_duplicate_blocker_cannot_be_approved_away(pg_client, pg_engine):
    original = prepared(pg_client, pg_engine)
    duplicate = upload_fixture(pg_client, "duplicate-altered.pdf")
    process(pg_client, duplicate)
    assert action(pg_client, duplicate, "review", decision="APPROVE").status_code == 409
    assert action(pg_client, duplicate, "post").status_code == 409
    # Recompute checks inside post: the original's old READY snapshot is now stale.
    assert action(pg_client, original, "post").status_code == 409
    assert detail(pg_client, original)["status"] == "NEEDS_REVIEW"
    rejected = action(pg_client, duplicate, "review", decision="REJECT", notes="Duplicate resend")
    assert rejected.json()["status"] == "REJECTED"
    action(pg_client, original, "revalidate")
    assert action(pg_client, original, "review", decision="APPROVE").status_code == 200
    assert action(pg_client, original, "post").status_code == 200
    assert action(pg_client, duplicate, "post").status_code == 409


def test_unknown_vendor_registration_is_audited_and_does_not_waive_rules(pg_client, pg_engine):
    invoice_id = prepared(pg_client, pg_engine, "unknown-vendor-1.pdf")
    assert action(pg_client, invoice_id, "review", decision="APPROVE").status_code == 409
    created = pg_client.post(
        "/api/v1/vendors",
        **operator_auth(pg_client),
        json={
            "display_name": "Unregistered Supplier 1",
            "expected_currency": "USD",
            "baseline_amount_limit": "5000.00",
            "is_approved": True,
        },
    )
    assert created.status_code == 201
    assert (
        pg_client.post(
            "/api/v1/vendors",
            **operator_auth(pg_client),
            json={
                "display_name": " unregistered  SUPPLIER 1 ",
            },
        ).status_code
        == 409
    )
    assert action(pg_client, invoice_id, "revalidate").json()["status"] == "NEEDS_REVIEW"
    assert action(pg_client, invoice_id, "post").status_code == 409
    assert action(pg_client, invoice_id, "review", decision="APPROVE").status_code == 200
    assert action(pg_client, invoice_id, "post").status_code == 200
    with Session(pg_engine) as session:
        events = session.scalars(
            select(AuditEvent).where(AuditEvent.event_type == "VENDOR_CREATED")
        ).all()
        assert any(
            e.actor == AUTH[0] and e.details["display_name"] == "Unregistered Supplier 1"
            for e in events
        )


def test_post_rechecks_changed_vendor_policy(pg_client, pg_engine):
    invoice_id = prepared(pg_client, pg_engine)
    with Session(pg_engine) as session:
        vendor = session.scalar(
            select(Vendor).where(Vendor.normalized_name == "alpha office supplies")
        )
        vendor.is_approved = False
        session.commit()
    result = action(pg_client, invoice_id, "post")
    assert result.status_code == 409 and "UNAPPROVED_VENDOR" in result.json()["error"]["message"]
    invoice = detail(pg_client, invoice_id)
    assert invoice["status"] == "NEEDS_REVIEW"
    assert any(
        r["rule_code"] == "UNAPPROVED_VENDOR" and not r["passed"] for r in invoice["validations"]
    )


def test_approval_is_bound_to_payload_hash_not_only_revision(pg_client, pg_engine):
    invoice_id = prepared(pg_client, pg_engine, "wrong-total.pdf")
    correction(pg_client, invoice_id, total="2300.00")
    action(pg_client, invoice_id, "revalidate", revision=2)
    action(pg_client, invoice_id, "review", revision=2, decision="APPROVE")
    # Simulate a future application bug that edits data without a revision bump.
    with Session(pg_engine) as session:
        invoice = session.get(Invoice, uuid.UUID(invoice_id))
        invoice.current_data = {**invoice.current_data, "due_date": "2026-12-01"}
        session.commit()
    assert (
        action(pg_client, invoice_id, "post", revision=2).json()["error"]["code"]
        == "APPROVAL_REQUIRED"
    )


def test_simultaneous_post_retries_produce_one_ledger_row(pg_client, pg_engine):
    invoice_id = prepared(pg_client, pg_engine)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: action(pg_client, invoice_id, "post"), range(4)))
    assert [r.status_code for r in results] == [200] * 4
    assert len({r.json()["id"] for r in results}) == 1
    with Session(pg_engine) as session:
        assert session.scalar(select(func.count()).select_from(LedgerEntry)) == 1
        assert (
            session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.event_type == "LEDGER_POSTED")
            )
            == 1
        )


def test_simultaneous_corrections_allow_one_current_revision(pg_client, pg_engine):
    invoice_id = prepared(pg_client, pg_engine)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda value: correction(pg_client, invoice_id, due_date=value),
                ["2026-12-01", "2026-12-02"],
            )
        )
    assert sorted(r.status_code for r in results) == [200, 409]
    assert detail(pg_client, invoice_id)["revision"] == 2


def test_simultaneous_approval_is_idempotent(pg_client, pg_engine):
    invoice_id = prepared(pg_client, pg_engine)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: action(pg_client, invoice_id, "review", decision="APPROVE"), range(2)
            )
        )
    assert [r.status_code for r in results] == [200, 200]
    assert len({r.json()["review_id"] for r in results}) == 1
    with Session(pg_engine) as session:
        assert session.scalar(select(func.count()).select_from(InvoiceReview)) == 1


def test_ledger_transaction_rolls_back_when_audit_write_fails(
    pg_client, pg_engine, settings, monkeypatch
):
    invoice_id = prepared(pg_client, pg_engine)
    before = detail(pg_client, invoice_id)

    def fail(*args, **kwargs):
        raise RuntimeError("Simulated ledger audit failure")

    monkeypatch.setattr("app.modules.ledger.service.record_event", fail)
    with Session(pg_engine) as session:
        with pytest.raises(RuntimeError, match="Simulated ledger audit failure"):
            post_invoice(
                session,
                uuid.UUID(invoice_id),
                RevisionRequest(expected_revision=1),
                settings,
                AUTH[0],
            )
    after = detail(pg_client, invoice_id)
    assert after["status"] == "READY_TO_POST"
    assert after["validation_run_id"] == before["validation_run_id"]
    with Session(pg_engine) as session:
        assert session.scalar(select(func.count()).select_from(LedgerEntry)) == 0


def test_database_uniqueness_is_guard_even_if_precheck_is_bypassed(
    pg_client, pg_engine, monkeypatch
):
    invoice_id = prepared(pg_client, pg_engine, "clean-002.pdf")
    other_id = upload_fixture(pg_client)
    with Session(pg_engine) as session:
        invoice = session.get(Invoice, uuid.UUID(invoice_id))
        session.add(
            LedgerEntry(
                invoice_id=uuid.UUID(other_id),
                vendor_id=invoice.vendor_id,
                invoice_number_normalized=invoice.normalized_invoice_number,
                currency="USD",
                total="1.00",
                posted_by="legacy-import",
            )
        )
        session.commit()

    def bypass(session, invoice, settings, actor):
        return parse_extraction(invoice.current_data), []

    monkeypatch.setattr("app.modules.ledger.service.validate_for_action", bypass)
    result = action(pg_client, invoice_id, "post")
    assert result.status_code == 409 and result.json()["error"]["code"] == "LEDGER_CONFLICT"
    assert detail(pg_client, invoice_id)["status"] == "NEEDS_REVIEW"
    with Session(pg_engine) as session:
        assert session.scalar(select(func.count()).select_from(LedgerEntry)) == 1
        assert (
            session.scalar(
                select(func.count())
                .select_from(LedgerEntry)
                .where(LedgerEntry.invoice_id == uuid.UUID(invoice_id))
            )
            == 0
        )


def test_posted_and_rejected_invoices_are_terminal(pg_client, pg_engine):
    posted = prepared(pg_client, pg_engine)
    action(pg_client, posted, "post")
    rejected = upload_fixture(pg_client, "wrong-total.pdf")
    process(pg_client, rejected)
    rejection = action(
        pg_client, rejected, "review", decision="REJECT", notes="Incorrect source total"
    )
    assert rejection.status_code == 200
    assert (
        action(
            pg_client, rejected, "review", decision="REJECT", notes="Incorrect source total"
        ).json()
        == rejection.json()
    )
    assert (
        action(
            pg_client, rejected, "review", decision="REJECT", notes="Change immutable reason"
        ).status_code
        == 409
    )
    for invoice_id in (posted, rejected):
        assert correction(pg_client, invoice_id, total="1.00").status_code == 409
        assert action(pg_client, invoice_id, "revalidate").status_code == 409
        assert action(pg_client, invoice_id, "review", decision="APPROVE").status_code == 409
    assert action(pg_client, rejected, "post").status_code == 409


def test_invalid_patches_notes_actor_spoofing_and_auth(pg_client, pg_engine):
    invoice_id = prepared(pg_client, pg_engine)
    for changes in ({"status": "POSTED"}, {"total": 1.15}, {"line_items": "bad"}):
        assert (
            pg_client.patch(
                f"/api/v1/invoices/{invoice_id}",
                **operator_auth(pg_client),
                json={"expected_revision": 1, "changes": changes},
            ).status_code
            == 422
        )
    for body in (
        {"decision": "REJECT", "notes": "  "},
        {"decision": "APPROVE", "reviewer": "spoofed"},
        {"decision": "APPROVE", "force": True},
    ):
        assert action(pg_client, invoice_id, "review", **body).status_code == 422
    for suffix in ("review", "post", "revalidate"):
        assert (
            pg_client.post(
                f"/api/v1/invoices/{invoice_id}/{suffix}", json={"expected_revision": 1}
            ).status_code
            == 401
        )
    assert (
        pg_client.patch(
            f"/api/v1/invoices/{invoice_id}",
            json={"expected_revision": 1, "changes": {"total": "1"}},
        ).status_code
        == 401
    )
    assert (
        pg_client.post("/api/v1/vendors", json={"display_name": "Unauthorized"}).status_code == 401
    )
    for path in ("/api/v1/ledger", "/api/v1/ledger/export.csv", "/api/v1/stats"):
        assert pg_client.get(path).status_code == 401


def test_only_latest_validation_batch_is_visible_but_history_remains(pg_client, pg_engine):
    invoice_id = prepared(pg_client, pg_engine)
    before = detail(pg_client, invoice_id)
    action(pg_client, invoice_id, "revalidate")
    after = detail(pg_client, invoice_id)
    assert before["validation_run_id"] != after["validation_run_id"]
    assert len(before["validations"]) == len(after["validations"])
    with Session(pg_engine) as session:
        assert (
            session.scalar(select(func.count()).select_from(ValidationResult))
            == len(after["validations"]) * 2
        )


def test_corrected_identity_is_used_before_revalidation(pg_client, pg_engine):
    invoice_id = prepared(pg_client, pg_engine)
    correction(pg_client, invoice_id, invoice_number="INV-NEW-001")
    peer = upload_fixture(pg_client, "duplicate-altered.pdf")
    assert process(pg_client, peer).json()["status"] == "READY_TO_POST"


def test_review_and_ledger_history_are_immutable_in_database(pg_client, pg_engine):
    invoice_id = prepared(pg_client, pg_engine)
    action(pg_client, invoice_id, "review", decision="APPROVE")
    action(pg_client, invoice_id, "post")
    for statement in (
        "UPDATE invoice_reviews SET notes='changed'",
        "DELETE FROM invoice_reviews",
        "UPDATE ledger_entries SET total=0",
        "DELETE FROM ledger_entries",
    ):
        with pytest.raises(DatabaseError, match="append-only"):
            with pg_engine.begin() as connection:
                connection.execute(text(statement))


def test_vendor_policy_request_validation(pg_client):
    for body in (
        {"display_name": "  "},
        {"display_name": "Supplier", "baseline_amount_limit": "100"},
        {"display_name": "Supplier", "expected_currency": "JPY", "baseline_amount_limit": "1.01"},
        {"display_name": "Supplier", "baseline_amount_limit": -1},
        {"display_name": "Supplier", "is_approved": "yes"},
    ):
        assert (
            pg_client.post("/api/v1/vendors", **operator_auth(pg_client), json=body).status_code
            == 422
        )
