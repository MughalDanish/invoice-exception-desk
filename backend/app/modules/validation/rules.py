import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, localcontext

from app.db.models import Severity
from app.modules.extraction.schemas import InvoiceExtraction

# Only currencies that fit the MVP ledger's numeric(18,2) are supported.
PRECISION = {"USD": 2, "EUR": 2, "GBP": 2, "JPY": 0}


def normalize(value: str | None) -> str:
    return " ".join(unicodedata.normalize("NFKC", value or "").casefold().split())


@dataclass(frozen=True)
class VendorPolicy:
    approved: bool
    currency: str | None
    amount_limit: Decimal | None


@dataclass(frozen=True)
class Rule:
    code: str
    passed: bool
    message: str
    expected: dict | None = None
    observed: dict | None = None
    severity: Severity = Severity.BLOCKER


def check_invoice(
    data: InvoiceExtraction,
    vendor: VendorPolicy | None,
    duplicate: bool = False,
    usd_tolerance: Decimal = Decimal("0.01"),
) -> list[Rule]:
    with localcontext() as context:
        context.prec = 64
        return _check_invoice(data, vendor, duplicate, usd_tolerance)


def _check_invoice(data, vendor, duplicate, usd_tolerance):
    rules = []

    def add(code, passed, message, expected=None, observed=None):
        rules.append(Rule(code, bool(passed), message, expected, observed))

    required = ("vendor_name", "invoice_number", "invoice_date", "currency", "total")
    missing = [
        key
        for key in required
        if getattr(data, key) is None
        or (isinstance(getattr(data, key), str) and not getattr(data, key).strip())
    ]
    add(
        "MISSING_REQUIRED_FIELD",
        not missing,
        "Required invoice fields",
        {"fields": list(required)},
        {"missing": missing},
    )
    parsed_dates = {}
    invalid_dates = []
    for field in ("invoice_date", "due_date"):
        value = getattr(data, field)
        if value is not None:
            try:
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                    raise ValueError()
                parsed_dates[field] = date.fromisoformat(value)
            except ValueError:
                invalid_dates.append(field)
    add(
        "INVALID_DATE",
        not invalid_dates,
        "Dates must be valid ISO calendar dates",
        observed={"invalid_fields": invalid_dates},
    )
    order_ok = not (parsed_dates.get("invoice_date") and parsed_dates.get("due_date")) or (
        parsed_dates["due_date"] >= parsed_dates["invoice_date"]
    )
    add("INVALID_DATE_RANGE", order_ok, "Due date must not precede invoice date")
    currency = (data.currency or "").strip().upper()
    supported = currency in PRECISION
    add(
        "UNSUPPORTED_CURRENCY",
        supported,
        "Currency must be supported by the demo ledger",
        {"currencies": list(PRECISION)},
        {"currency": currency},
    )
    quantum = Decimal(1).scaleb(-PRECISION.get(currency, 2))
    tolerance = (
        usd_tolerance if currency == "USD" else (Decimal(0) if currency == "JPY" else quantum)
    )

    def rounded(value):
        return value.quantize(quantum, rounding=ROUND_HALF_UP)

    monetary = [data.subtotal, data.tax_amount, data.total]
    monetary.extend(item.line_total for item in data.line_items)
    precise = supported and all(value is None or value == rounded(value) for value in monetary)
    add("MONEY_PRECISION", precise, "Amounts must use the currency's minor-unit precision")
    add(
        "AMOUNT_RANGE",
        all(v is None or abs(v) <= Decimal("9999999999999999.99") for v in monetary),
        "Amounts must fit the ledger's numeric(18,2) range",
    )
    values = monetary + [data.tax_rate]
    for item in data.line_items:
        values.extend([item.quantity, item.unit_price])
    add(
        "NEGATIVE_AMOUNT",
        all(v is None or v >= 0 for v in values),
        "Negative invoices and credit notes are outside the MVP",
    )
    add(
        "INVALID_TAX_RATE",
        data.tax_rate is None or data.tax_rate <= 1,
        "Explicit tax rate must be a fraction between zero and one",
    )
    incomplete = (
        not data.line_items
        or any(v is None for v in (data.subtotal, data.tax_amount, data.total))
        or any(
            any(v is None for v in (item.quantity, item.unit_price, item.line_total))
            for item in data.line_items
        )
    )
    add(
        "ARITHMETIC_INCOMPLETE",
        not incomplete,
        "Line items, subtotal, tax amount, and total must be available for arithmetic checks",
    )
    line_errors = []
    for index, item in enumerate(data.line_items):
        if all(v is not None for v in (item.quantity, item.unit_price, item.line_total)):
            expected = rounded(item.quantity * item.unit_price)
            if abs(expected - item.line_total) > tolerance:
                line_errors.append(
                    {"line": index + 1, "expected": str(expected), "observed": str(item.line_total)}
                )
    add(
        "LINE_TOTAL_MISMATCH",
        not line_errors,
        "Quantity times unit price must match line total",
        observed={"mismatches": line_errors},
    )
    if (
        data.line_items
        and all(i.line_total is not None for i in data.line_items)
        and data.subtotal is not None
    ):
        expected = sum((i.line_total for i in data.line_items), Decimal(0))
        add(
            "SUBTOTAL_MISMATCH",
            abs(expected - data.subtotal) <= tolerance,
            "Line totals must sum to subtotal",
            {"amount": str(expected)},
            {"amount": str(data.subtotal)},
        )
    if all(v is not None for v in (data.subtotal, data.tax_amount, data.total)):
        expected = data.subtotal + data.tax_amount
        add(
            "TOTAL_MISMATCH",
            abs(expected - data.total) <= tolerance,
            "Subtotal plus tax must equal total",
            {"amount": str(expected)},
            {"amount": str(data.total)},
        )
    if data.tax_rate is not None and data.subtotal is not None and data.tax_amount is not None:
        expected = rounded(data.subtotal * data.tax_rate)
        add(
            "TAX_RATE_MISMATCH",
            abs(expected - data.tax_amount) <= tolerance,
            "Explicit tax rate times subtotal must equal tax amount",
            {"amount": str(expected)},
            {"amount": str(data.tax_amount)},
        )
    add("UNAPPROVED_VENDOR", vendor is not None and vendor.approved, "Supplier must be approved")
    add("DUPLICATE_INVOICE", not duplicate, "Supplier and invoice number must be unique")
    add(
        "CURRENCY_MISMATCH",
        vendor is None or vendor.currency is None or currency == vendor.currency,
        "Currency must match supplier policy",
        {"currency": vendor.currency if vendor else None},
        {"currency": currency},
    )
    # Never compare thresholds expressed in another currency.
    comparable = (
        vendor is not None and vendor.currency == currency and vendor.amount_limit is not None
    )
    add(
        "AMOUNT_OUTLIER",
        not comparable or data.total is None or data.total <= vendor.amount_limit,
        "Total must not exceed the supplier's configured threshold",
    )
    uncertain = list(data.uncertain_fields)
    for field in ("invoice_number", "total"):
        if getattr(data, field) is not None and not data.evidence.get(field, "").strip():
            uncertain.append(field)
    add(
        "UNCERTAIN_EXTRACTION",
        not uncertain,
        "Uncertain fields or missing source evidence need correction",
        observed={"fields": sorted(set(uncertain))},
    )
    return rules
