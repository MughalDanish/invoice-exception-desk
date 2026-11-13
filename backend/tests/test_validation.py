import copy
import json
from decimal import Decimal

import pytest

from app.db.models import Severity
from app.modules.extraction.adapters import ExtractionError, parse_extraction
from app.modules.validation.rules import VendorPolicy, check_invoice, normalize
from tests.conftest import ROOT


@pytest.fixture
def payload():
    return copy.deepcopy(
        json.loads((ROOT / "fixtures/answers.json").read_text())["fixtures"]["clean-001.pdf"][
            "extraction"
        ]
    )


POLICY = VendorPolicy(True, "USD", Decimal("5000.00"))


def blockers(payload, policy=POLICY, duplicate=False):
    return {
        r.code
        for r in check_invoice(parse_extraction(payload), policy, duplicate)
        if not r.passed and r.severity == Severity.BLOCKER
    }


def test_clean_invoice_has_no_blockers(payload):
    assert blockers(payload) == set()


@pytest.mark.parametrize(
    "updates,expected",
    [
        ({"total": "1250.00"}, "TOTAL_MISMATCH"),
        ({"subtotal": "1001.00"}, "SUBTOTAL_MISMATCH"),
        ({"tax_rate": "0.10"}, "TAX_RATE_MISMATCH"),
        ({"invoice_number": None}, "MISSING_REQUIRED_FIELD"),
        ({"vendor_name": "  "}, "MISSING_REQUIRED_FIELD"),
        ({"invoice_date": "2026-02-30"}, "INVALID_DATE"),
        ({"invoice_date": "13/11/2026"}, "INVALID_DATE"),
        ({"due_date": "2026-11-12"}, "INVALID_DATE_RANGE"),
        ({"currency": "ZZZ"}, "UNSUPPORTED_CURRENCY"),
        ({"currency": "EUR"}, "CURRENCY_MISMATCH"),
        ({"total": "5000.01"}, "AMOUNT_OUTLIER"),
        ({"line_items": []}, "ARITHMETIC_INCOMPLETE"),
        ({"subtotal": None}, "ARITHMETIC_INCOMPLETE"),
        ({"tax_amount": None}, "ARITHMETIC_INCOMPLETE"),
        ({"total": "1150.001"}, "MONEY_PRECISION"),
        ({"total": "-1150.00"}, "NEGATIVE_AMOUNT"),
        ({"tax_rate": "15"}, "INVALID_TAX_RATE"),
        ({"uncertain_fields": ["total"]}, "UNCERTAIN_EXTRACTION"),
        ({"evidence": {}}, "UNCERTAIN_EXTRACTION"),
        ({"total": "999999999999999999"}, "AMOUNT_RANGE"),
    ],
)
def test_business_rule_failures(payload, updates, expected):
    payload.update(updates)
    assert expected in blockers(payload)


def test_line_math_and_missing_line_fields(payload):
    payload["line_items"][0]["quantity"] = "9"
    assert "LINE_TOTAL_MISMATCH" in blockers(payload)
    payload["line_items"][0]["quantity"] = None
    assert "ARITHMETIC_INCOMPLETE" in blockers(payload)


def test_large_line_multiplication_does_not_crash(payload):
    payload["line_items"][0].update(quantity="999999999999999999", unit_price="999999999999999999")
    assert "LINE_TOTAL_MISMATCH" in blockers(payload)


def test_no_tax_rate_is_inferred(payload):
    payload["tax_rate"] = None
    assert blockers(payload) == set()


@pytest.mark.parametrize("policy", [None, VendorPolicy(False, "USD", Decimal("5000"))])
def test_supplier_must_be_approved(payload, policy):
    assert "UNAPPROVED_VENDOR" in blockers(payload, policy)


def test_business_duplicate_does_not_depend_on_amount(payload):
    assert "DUPLICATE_INVOICE" in blockers(payload, duplicate=True)


def test_do_not_compare_amounts_across_currencies(payload):
    payload["currency"] = "JPY"
    payload["total"] = "100000"
    assert "CURRENCY_MISMATCH" in blockers(payload)
    assert "AMOUNT_OUTLIER" not in blockers(payload)


def test_currency_precision_and_tolerance(payload):
    payload["total"] = "1150.01"
    assert "TOTAL_MISMATCH" not in blockers(payload)
    payload["total"] = "1150.02"
    assert "TOTAL_MISMATCH" in blockers(payload)
    payload.update(currency="JPY", total="1150.01")
    codes = blockers(payload, VendorPolicy(True, "JPY", Decimal("5000")))
    assert {"TOTAL_MISMATCH", "MONEY_PRECISION"} <= codes


@pytest.mark.parametrize("value", [1.15, True, "NaN", "Infinity", "1e100"])
def test_invalid_financial_types_are_not_accepted(payload, value):
    payload["total"] = value
    with pytest.raises(ExtractionError, match="INVALID_EXTRACTION_OUTPUT"):
        parse_extraction(payload)


def test_normalization_is_explicit_not_fuzzy():
    assert normalize("  ＡLPHA  Office SUPPLIES ") == "alpha office supplies"
    assert normalize(" INV-A-001 ") == "inv-a-001"
    assert normalize("Alpha Office") != normalize("Alpha-Office")


def test_unusable_output_and_unknown_actions_are_rejected(payload):
    with pytest.raises(ExtractionError, match="UNUSABLE_EXTRACTION"):
        parse_extraction({})
    payload["approve_payment"] = True
    with pytest.raises(ExtractionError, match="INVALID_EXTRACTION_OUTPUT"):
        parse_extraction(payload)
