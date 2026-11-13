import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class LedgerSummary(BaseModel):
    id: uuid.UUID
    invoice_id: uuid.UUID
    vendor_name: str
    invoice_number: str
    invoice_date: str | None
    invoice_revision: int | None
    currency: str
    total: Decimal
    posted_at: datetime
    posted_by: str


class LedgerPage(BaseModel):
    items: list[LedgerSummary]
    page: int
    limit: int
    total: int


def ledger_summary(entry, vendor_name=""):
    snapshot = entry.snapshot or {}
    data = snapshot.get("data") or {}
    return LedgerSummary(
        id=entry.id,
        invoice_id=entry.invoice_id,
        vendor_name=data.get("vendor_name") or vendor_name,
        invoice_number=data.get("invoice_number") or entry.invoice_number_normalized,
        invoice_date=data.get("invoice_date"),
        invoice_revision=snapshot.get("revision"),
        currency=entry.currency,
        total=entry.total,
        posted_at=entry.posted_at,
        posted_by=entry.posted_by,
    )
