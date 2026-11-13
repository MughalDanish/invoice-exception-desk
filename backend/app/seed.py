"""Idempotent Day 1 seed: three suppliers and synthetic, unprocessed invoices."""

import argparse
import json
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.core.config import Settings
from app.db.models import Source, Vendor
from app.db.session import build_engine, build_session_factory
from app.modules.audit.service import record_event
from app.modules.invoices.service import ingest_file
from app.modules.invoices.storage import validate_file

VENDORS = [
    ("Alpha Office Supplies", "USD", "5000.00"),
    ("Beta Tech", "USD", "10000.00"),
    ("Gamma Building Materials", "USD", "20000.00"),
]


def seed_vendors(session):
    with session.begin():
        session.execute(select(func.pg_advisory_xact_lock(48521001)))
        for name, currency, threshold in VENDORS:
            row_id = session.scalar(
                insert(Vendor)
                .values(
                    normalized_name=name.casefold(),
                    display_name=name,
                    expected_currency=currency,
                    baseline_amount_limit=Decimal(threshold),
                    is_approved=True,
                )
                .on_conflict_do_nothing(index_elements=[Vendor.normalized_name])
                .returning(Vendor.id)
            )
            if row_id:
                record_event(
                    session,
                    "fixture-seed",
                    "VENDOR_CREATED",
                    details={
                        "vendor_id": str(row_id),
                        "display_name": name,
                    },
                )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="Ingest all synthetic fixture PDFs")
    args = parser.parse_args()
    settings = Settings()
    engine = build_engine(settings.database_url)
    try:
        with build_session_factory(engine)() as session:
            seed_vendors(session)
            manifest = json.loads(
                (settings.fixtures_dir / "answers.json").read_text(encoding="utf-8")
            )
            filenames = list(manifest["fixtures"]) if args.all else ["clean-001.pdf"]
            for filename in filenames:
                content = (settings.fixtures_dir / "invoices" / filename).read_bytes()
                validated = validate_file(
                    filename, "application/pdf", content, settings.max_upload_bytes
                )
                invoice, duplicate = ingest_file(
                    session,
                    validated,
                    settings.storage_dir,
                    "fixture-seed",
                    Source.fixture,
                )
                print(
                    json.dumps(
                        {
                            "invoice_id": str(invoice.id),
                            "filename": filename,
                            "status": invoice.status.value,
                            "duplicate": duplicate,
                        }
                    )
                )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
