"""Capture bounded exact SQL lookups; scope comes from the locked invoice, never a plan."""

from sqlalchemy import select

from app.db.models import Invoice, InvoiceStatus, LedgerEntry, Vendor
from app.modules.approvals.service import payload_hash
from app.modules.investigation.schemas import (
    DuplicateCandidate,
    LedgerFact,
    LookupSnapshot,
    SupplierPolicy,
    exact_amount,
)


def capture_lookups(session, invoice) -> LookupSnapshot:
    supplier_key = invoice.normalized_vendor_name or ""
    invoice_key = invoice.normalized_invoice_number or ""
    policy = (
        session.scalar(
            select(Vendor)
            .where(Vendor.normalized_name == supplier_key)
            .execution_options(populate_existing=True)
        )
        if supplier_key
        else None
    )
    peers = (
        session.scalars(
            select(Invoice)
            .where(
                Invoice.id != invoice.id,
                Invoice.normalized_vendor_name == supplier_key,
                Invoice.normalized_invoice_number == invoice_key,
                Invoice.status.not_in([InvoiceStatus.REJECTED, InvoiceStatus.EXTRACTION_FAILED]),
            )
            .order_by(Invoice.id)
            .limit(21)
            .execution_options(populate_existing=True)
        ).all()
        if supplier_key and invoice_key
        else []
    )
    matches = (
        session.scalars(
            select(LedgerEntry)
            .where(
                LedgerEntry.vendor_id == policy.id,
                LedgerEntry.invoice_number_normalized == invoice_key,
                LedgerEntry.invoice_id != invoice.id,
            )
            .order_by(LedgerEntry.id)
            .limit(21)
        ).all()
        if policy and invoice_key
        else []
    )
    history = (
        session.scalars(
            select(LedgerEntry)
            .where(
                LedgerEntry.vendor_id == policy.id,
                LedgerEntry.currency == (invoice.current_data or {}).get("currency"),
            )
            .order_by(LedgerEntry.posted_at.desc(), LedgerEntry.id)
            .limit(21)
        ).all()
        if policy
        else []
    )

    def ledger_facts(rows):
        return tuple(
            LedgerFact(id=row.id, currency=row.currency, total=str(row.total)) for row in rows[:20]
        )

    return LookupSnapshot(
        supplier_key=supplier_key,
        invoice_key=invoice_key,
        invoice_total=exact_amount((invoice.current_data or {}).get("total")),
        policy=SupplierPolicy(
            id=policy.id,
            approved=policy.is_approved,
            currency=policy.expected_currency,
            amount_limit=exact_amount(str(policy.baseline_amount_limit)),
        )
        if policy
        else None,
        duplicates=tuple(
            DuplicateCandidate(
                id=row.id,
                revision=row.revision,
                status=row.status.value,
                payload_hash=payload_hash(row.current_data),
            )
            for row in peers[:20]
        ),
        ledger_matches=ledger_facts(matches),
        history=ledger_facts(history),
        duplicates_truncated=len(peers) > 20,
        ledger_matches_truncated=len(matches) > 20,
        history_truncated=len(history) > 20,
    )
