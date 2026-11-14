import csv
import io
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Vendor
from app.modules.extraction.adapters import get_extractor
from app.modules.ledger.export import safe_cell
from tests.conftest import operator_auth
from tests.test_processing import FixedExtractor, clean_payload, process, upload_fixture
from tests.test_review_posting import action, prepared


@pytest.mark.parametrize(
    "cell",
    [
        "=SUM(A1:A2)",
        "+cmd",
        "-formula",
        "@SUM(1,2)",
        " \t=1+1",
        "\tordinary",
        "\nformula",
        "\ufeff=1+1",
        "＝1+1",
        "\u00a0@a",
    ],
)
def test_formula_cells_are_forced_to_text(cell):
    assert safe_cell(cell) == "'" + cell


def test_safe_text_and_decimal_cells_are_preserved():
    assert safe_cell('Supplier, "Quoted"\nSecond line') == 'Supplier, "Quoted"\nSecond line'
    assert safe_cell("1150.00") == "1150.00"
    assert safe_cell(None) == ""


def test_mixed_unicode_whitespace_and_bom_cannot_hide_formula():
    value = "\u1680\ufeff\u200b \t=1+1"
    assert safe_cell(value) == "'" + value


@pytest.mark.postgres
def test_csv_is_quoted_snapshot_based_and_only_includes_posted(pg_client, pg_engine):
    invoice_id = prepared(pg_client, pg_engine)
    assert action(pg_client, invoice_id, "post").status_code == 200
    withheld = upload_fixture(pg_client, "wrong-total.pdf")
    process(pg_client, withheld)
    with Session(pg_engine) as session:
        vendor = session.scalar(
            select(Vendor).where(Vendor.normalized_name == "alpha office supplies")
        )
        vendor.display_name = "Changed registry display"
        session.commit()
    result = pg_client.get("/api/v1/ledger/export.csv", **operator_auth(pg_client))
    assert result.status_code == 200
    assert result.headers["cache-control"] == "no-store"
    assert f"invoice-ledger-{datetime.now(UTC):%Y%m%d}.csv" in result.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(result.content.decode("utf-8-sig"), newline="")))
    assert len(rows) == 1 and rows[0]["invoice_id"] == invoice_id
    assert rows[0]["vendor"] == "Alpha Office Supplies" and rows[0]["total"] == "1150.00"
    assert pg_client.get("/api/v1/ledger?limit=1", **operator_auth(pg_client)).json()["total"] == 1
    assert (
        pg_client.get("/api/v1/ledger?page=2&limit=1", **operator_auth(pg_client)).json()["items"]
        == []
    )
    assert pg_client.get("/api/v1/ledger?limit=101", **operator_auth(pg_client)).status_code == 422
    stats = pg_client.get("/api/v1/stats", **operator_auth(pg_client)).json()
    assert stats["by_status"]["POSTED"] == 1
    assert stats["by_status"]["NEEDS_REVIEW"] == 1
    assert stats["posted_totals_by_currency"] == {"USD": "1150.00"}
    assert stats["flagged_totals_by_currency"] == {"USD": "2500.00"}


@pytest.mark.postgres
def test_csv_round_trips_quotes_newlines_and_neutralizes_formula(pg_client, pg_engine):
    vendor_name = 'Supplier, "Quoted"\nSecond line'
    assert (
        pg_client.post(
            "/api/v1/vendors",
            **operator_auth(pg_client),
            json={
                "display_name": vendor_name,
                "expected_currency": "USD",
                "baseline_amount_limit": "5000.00",
            },
        ).status_code
        == 201
    )
    payload = clean_payload()
    payload.update(vendor_name=vendor_name, invoice_number="=SUM(1,2)")
    pg_client.app.dependency_overrides[get_extractor] = lambda: FixedExtractor(payload)
    invoice_id = upload_fixture(pg_client)
    assert process(pg_client, invoice_id).json()["status"] == "READY_TO_POST"
    assert action(pg_client, invoice_id, "post").status_code == 200
    result = pg_client.get("/api/v1/ledger/export.csv", **operator_auth(pg_client))
    rows = list(csv.DictReader(io.StringIO(result.content.decode("utf-8-sig"), newline="")))
    assert rows[0]["vendor"] == vendor_name
    assert rows[0]["invoice_number"] == "'=SUM(1,2)"
    assert '"Supplier, ""Quoted""\nSecond line"' in result.content.decode("utf-8-sig")


@pytest.mark.postgres
def test_empty_export_contains_only_header(pg_client):
    rows = list(
        csv.reader(
            io.StringIO(
                pg_client.get(
                    "/api/v1/ledger/export.csv", **operator_auth(pg_client)
                ).content.decode("utf-8-sig")
            )
        )
    )
    assert len(rows) == 1 and rows[0][0] == "ledger_id"
