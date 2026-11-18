import concurrent.futures
import uuid

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import func, select, text
from sqlalchemy.exc import DatabaseError, IntegrityError
from sqlalchemy.orm import Session

from alembic import command
from app.db.base import Base
from app.db.models import AuditEvent, Invoice, LedgerEntry, Vendor
from app.modules.invoices.service import ingest_file
from app.modules.invoices.storage import validate_file
from app.seed import seed_vendors
from tests.conftest import AUTH, ROOT, operator_auth

pytestmark = pytest.mark.postgres


def upload(client, content):
    return client.post(
        "/api/v1/invoices/upload",
        **operator_auth(client),
        files={"file": ("invoice.pdf", content, "application/pdf")},
    )


def test_health_and_complete_upload_read_flow(pg_client, clean_pdf, settings):
    assert pg_client.get("/health").json()["database"] == "ready"
    result = upload(pg_client, clean_pdf)
    assert result.status_code == 201
    invoice_id = result.json()["invoice_id"]
    assert result.json()["status"] == "RECEIVED"
    detail = pg_client.get(f"/api/v1/invoices/{invoice_id}", **operator_auth(pg_client)).json()
    assert detail["revision"] == 1
    assert detail["byte_size"] == len(clean_pdf)
    assert detail["current_data"] is None
    assert "file_path" not in detail
    original = pg_client.get(f"/api/v1/invoices/{invoice_id}/file", **operator_auth(pg_client))
    assert original.content == clean_pdf
    assert original.headers["cache-control"] == "no-store"
    assert len(list(settings.storage_dir.iterdir())) == 1
    audit = pg_client.get(f"/api/v1/invoices/{invoice_id}/audit", **operator_auth(pg_client)).json()
    assert audit[0]["event_type"] == "INVOICE_RECEIVED"
    assert audit[0]["actor"] == AUTH[0]


def test_repeat_upload_returns_original_without_extra_file(pg_client, clean_pdf, settings):
    first = upload(pg_client, clean_pdf)
    second = upload(pg_client, clean_pdf)
    assert second.status_code == 200
    assert second.json()["duplicate"] is True
    assert second.json()["invoice_id"] == first.json()["invoice_id"]
    assert len(list(settings.storage_dir.iterdir())) == 1
    assert pg_client.get("/api/v1/invoices", **operator_auth(pg_client)).json()["total"] == 1


def test_concurrent_identical_uploads_one_row_and_one_file(
    pg_client, pg_engine, clean_pdf, settings
):
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: upload(pg_client, clean_pdf), range(4)))
    assert sorted(r.status_code for r in results) == [200, 200, 200, 201]
    assert len({r.json()["invoice_id"] for r in results}) == 1
    with Session(pg_engine) as session:
        assert session.scalar(select(func.count()).select_from(Invoice)) == 1
        assert session.scalar(select(func.count()).select_from(AuditEvent)) == 4
    assert len(list(settings.storage_dir.iterdir())) == 1


def test_pagination_filter_search_and_bad_parameters(pg_client, clean_pdf):
    upload(pg_client, clean_pdf)
    page = pg_client.get(
        "/api/v1/invoices?status=RECEIVED&search=voice&page=1&limit=1", **operator_auth(pg_client)
    )
    assert page.json()["total"] == 1
    assert len(page.json()["items"]) == 1
    assert (
        pg_client.get("/api/v1/invoices?search=%25", **operator_auth(pg_client)).json()["total"]
        == 0
    )
    assert (
        pg_client.get("/api/v1/invoices?status=POSTED", **operator_auth(pg_client)).json()["total"]
        == 0
    )
    assert (
        pg_client.get("/api/v1/invoices?page=2&limit=1", **operator_auth(pg_client)).json()["items"]
        == []
    )
    for query in ("limit=0", "limit=101", "page=0", "status=INVALID"):
        assert (
            pg_client.get("/api/v1/invoices?" + query, **operator_auth(pg_client)).status_code
            == 422
        )


def test_unknown_and_invalid_invoice_ids(pg_client):
    assert (
        pg_client.get(f"/api/v1/invoices/{uuid.uuid4()}", **operator_auth(pg_client)).status_code
        == 404
    )
    assert (
        pg_client.get("/api/v1/invoices/not-a-uuid", **operator_auth(pg_client)).status_code == 422
    )


def test_vendor_seed_is_repeatable_and_audited(pg_client, pg_engine):
    with Session(pg_engine) as session:
        seed_vendors(session)
        seed_vendors(session)
        assert session.scalar(select(func.count()).select_from(AuditEvent)) == 3
    vendors = pg_client.get("/api/v1/vendors", **operator_auth(pg_client)).json()
    assert len(vendors) == 3
    assert all(v["is_approved"] for v in vendors)
    assert vendors[0]["baseline_amount_limit"] == "5000.00"


def test_storage_cleanup_on_transaction_failure(pg_engine, settings, clean_pdf, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("Simulated audit failure")

    monkeypatch.setattr("app.modules.invoices.service.record_event", fail)
    file = validate_file("invoice.pdf", "application/pdf", clean_pdf, 8388608)
    with Session(pg_engine) as session:
        with pytest.raises(RuntimeError, match="Simulated audit failure"):
            ingest_file(session, file, settings.storage_dir, "operator")
        assert session.scalar(select(func.count()).select_from(Invoice)) == 0
    assert list(settings.storage_dir.iterdir()) == []


def test_database_disallows_audit_edits_and_deletes(pg_engine):
    with Session(pg_engine) as session:
        session.add(AuditEvent(actor="test", event_type="TEST", details={}))
        session.commit()
    for statement in ("UPDATE audit_events SET actor = 'changed'", "DELETE FROM audit_events"):
        with pytest.raises(DatabaseError, match="append-only"):
            with pg_engine.begin() as conn:
                conn.execute(text(statement))


def test_ledger_unique_constraints_prevent_duplicates(pg_client, pg_engine, clean_pdf):
    invoice_id = uuid.UUID(upload(pg_client, clean_pdf).json()["invoice_id"])
    with Session(pg_engine) as session:
        seed_vendors(session)
        vendor = session.scalar(select(Vendor).limit(1))
        values = dict(
            invoice_id=invoice_id,
            vendor_id=vendor.id,
            invoice_number_normalized="inv-a-001",
            currency="USD",
            total="1150.00",
            posted_by="test",
        )
        session.add(LedgerEntry(**values))
        session.commit()
        session.add(LedgerEntry(**values))
        with pytest.raises(IntegrityError):
            session.commit()


def test_migration_matches_orm(pg_engine):
    with pg_engine.connect() as connection:
        context = MigrationContext.configure(connection)
        assert compare_metadata(context, Base.metadata) == []


def test_ledger_vendor_number_unique_even_when_amount_changes(pg_client, pg_engine, clean_pdf):
    first_id = uuid.UUID(upload(pg_client, clean_pdf).json()["invoice_id"])
    second_pdf = (ROOT / "fixtures" / "invoices" / "clean-002.pdf").read_bytes()
    second_id = uuid.UUID(upload(pg_client, second_pdf).json()["invoice_id"])
    with Session(pg_engine) as session:
        seed_vendors(session)
        vendor = session.scalar(select(Vendor).limit(1))
        common = dict(
            vendor_id=vendor.id,
            invoice_number_normalized="inv-a-001",
            currency="USD",
            posted_by="test",
        )
        session.add(LedgerEntry(invoice_id=first_id, total="1150.00", **common))
        session.commit()
        session.add(LedgerEntry(invoice_id=second_id, total="2300.00", **common))
        with pytest.raises(IntegrityError, match="uq_ledger_vendor_number"):
            session.commit()
        session.rollback()
        assert session.scalar(select(func.count()).select_from(LedgerEntry)) == 1


def test_migration_downgrade_and_upgrade(pg_engine):
    with pg_engine.begin() as connection:
        config = Config(str(ROOT / "backend" / "alembic.ini"))
        config.attributes["connection"] = connection
        command.downgrade(config, "base")
        command.upgrade(config, "head")
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "0007_investigation_documents"
        )
