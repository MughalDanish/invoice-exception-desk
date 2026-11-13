import hashlib

from sqlalchemy import func, select

from app.db.models import Invoice, InvoiceStatus, LedgerEntry, ValidationResult, Vendor
from app.modules.validation.rules import VendorPolicy, check_invoice, normalize


def validate_current(session, invoice, data, tolerance):
    vendor_name = normalize(data.vendor_name)
    number = normalize(data.invoice_number)
    # Full-width/case transformations can expand text beyond storage limits.
    if len(vendor_name) > 200 or len(number) > 200:
        from app.modules.extraction.adapters import ExtractionError

        raise ExtractionError("NORMALIZED_IDENTITY_TOO_LONG")
    fingerprint = hashlib.sha256(f"{vendor_name}\x00{number}".encode()).digest()
    key = int.from_bytes(fingerprint[:8], "big", signed=True)
    session.execute(select(func.pg_advisory_xact_lock(key)))
    vendor = session.scalar(select(Vendor).where(Vendor.normalized_name == vendor_name))
    duplicate = False
    if vendor_name and number:
        duplicate = (
            session.scalar(
                select(Invoice.id)
                .where(
                    Invoice.id != invoice.id,
                    Invoice.normalized_vendor_name == vendor_name,
                    Invoice.normalized_invoice_number == number,
                    Invoice.status.not_in(
                        [InvoiceStatus.REJECTED, InvoiceStatus.EXTRACTION_FAILED]
                    ),
                )
                .limit(1)
            )
            is not None
        )
        if vendor is not None:
            duplicate = (
                duplicate
                or session.scalar(
                    select(LedgerEntry.id)
                    .where(
                        LedgerEntry.vendor_id == vendor.id,
                        LedgerEntry.invoice_number_normalized == number,
                        LedgerEntry.invoice_id != invoice.id,
                    )
                    .limit(1)
                )
                is not None
            )
    policy = (
        VendorPolicy(vendor.is_approved, vendor.expected_currency, vendor.baseline_amount_limit)
        if vendor
        else None
    )
    rules = check_invoice(data, policy, duplicate, tolerance)
    invoice.vendor_id = vendor.id if vendor else None
    invoice.normalized_vendor_name = vendor_name or None
    invoice.normalized_invoice_number = number or None
    for rule in rules:
        session.add(
            ValidationResult(
                invoice_id=invoice.id,
                revision=invoice.revision,
                rule_code=rule.code,
                severity=rule.severity,
                passed=rule.passed,
                message=rule.message,
                expected=rule.expected,
                observed=rule.observed,
            )
        )
    return rules
