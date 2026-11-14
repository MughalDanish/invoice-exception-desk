import json
from decimal import Decimal

import pytest
from google.genai import types

from app.modules.extraction.adapters import ExtractionError
from app.modules.extraction.response import logger, normalize_payload, parse_response
from app.modules.validation.rules import check_invoice


def response(text, reason="STOP"):
    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                finish_reason=reason, content=types.Content(parts=[types.Part(text=text)])
            )
        ]
    )


@pytest.mark.parametrize(
    "text,reason,code",
    [
        ("", "STOP", "GEMINI_EMPTY_RESPONSE"),
        ("   ", "STOP", "GEMINI_EMPTY_RESPONSE"),
        ('{"total":"1.00"}', "MAX_TOKENS", "GEMINI_RESPONSE_TRUNCATED"),
        ('{"total":', "STOP", "GEMINI_MALFORMED_JSON"),
        ("```json\n{}\n```", "STOP", "GEMINI_MALFORMED_JSON"),
        ("", "SAFETY", "GEMINI_RESPONSE_BLOCKED"),
    ],
)
def test_response_failures_are_distinct(text, reason, code):
    with pytest.raises(ExtractionError, match=code):
        parse_response(response(text, reason))


def test_no_candidates_is_empty():
    with pytest.raises(ExtractionError, match="GEMINI_EMPTY_RESPONSE"):
        parse_response(types.GenerateContentResponse())


def test_exact_display_normalization_preserves_source_and_precision():
    original = {
        "subtotal": "9,999,999,999,999.990000",
        "tax_rate": "5.00%",
        "line_items": [{"line_total": "1,234.560000"}],
        "total": "999.00",
    }
    normalized = normalize_payload(original)
    assert original["subtotal"] == "9,999,999,999,999.990000"
    assert original["line_items"][0]["line_total"] == "1,234.560000"
    assert normalized["subtotal"] == "9999999999999.990000"
    assert normalized["tax_rate"] == "0.0500"
    result = parse_response(response(json.dumps(original)))
    assert str(result.subtotal) == "9999999999999.990000"
    assert result.tax_rate == Decimal("0.0500")
    assert str(result.line_items[0].line_total) == "1234.560000"
    assert result.total == Decimal("999.00")


@pytest.mark.parametrize(
    "value", ["1,23.00", "1.234,56", "1,234", "$123.00", "NaN", "Infinity", "5%", 12.5, True]
)
def test_ambiguous_or_invalid_money_is_rejected(value):
    with pytest.raises(ExtractionError, match="INVALID_EXTRACTION_OUTPUT"):
        parse_response(response(json.dumps({"total": value})))


def test_missing_fields_remain_missing_and_arithmetic_is_not_repaired():
    data = parse_response(
        response(
            json.dumps(
                {"subtotal": "100.00", "tax_rate": "5%", "tax_amount": "8.00", "total": "115.00"}
            )
        )
    )
    assert data.vendor_name is None and data.line_items == []
    assert data.tax_amount == Decimal("8.00") and data.total == Decimal("115.00")
    rules = check_invoice(data, None)
    assert any(not rule.passed for rule in rules)


def test_validation_logs_never_contain_input_or_unknown_keys(caplog, monkeypatch):
    monkeypatch.setattr(logger, "disabled", False)
    caplog.set_level("WARNING", logger=logger.name)
    for payload in [
        {"total": "private-invoice-value"},
        {"total": "1.00", "private-key-as-invoice-content": "private-secret"},
    ]:
        with pytest.raises(ExtractionError, match="INVALID_EXTRACTION_OUTPUT"):
            parse_response(response(json.dumps(payload)))
    assert "private-invoice-value" not in caplog.text
    assert "private-key-as-invoice-content" not in caplog.text
    assert "private-secret" not in caplog.text
    assert "total" in caplog.text and "<unknown-field>" in caplog.text
    assert "decimal_parsing" in caplog.text and "extra_forbidden" in caplog.text
