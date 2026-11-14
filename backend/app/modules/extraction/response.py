"""Provider boundary: safe diagnostics and exact, explicit display-format normalization."""

import json
import logging
import re
from decimal import Decimal

from pydantic import ValidationError

from app.modules.extraction.adapters import ExtractionError, parse_extraction
from app.modules.extraction.gemini_schema import GeminiInvoice
from app.modules.extraction.schemas import InvoiceExtraction, LineItem

logger = logging.getLogger(__name__)
KNOWN_FIELDS = set(InvoiceExtraction.model_fields) | set(LineItem.model_fields)
GROUPED = re.compile(r"^[+-]?[0-9]{1,3}(?:,[0-9]{3})+\.[0-9]+$")
PERCENT = re.compile(r"^[+-]?[0-9]+(?:\.[0-9]+)?%$")


def validation_errors(exc):
    # Error messages, input, context, arbitrary keys and URLs may contain private data.
    return [
        {
            "path": [
                part if isinstance(part, int) or part in KNOWN_FIELDS else "<unknown-field>"
                for part in error["loc"]
            ],
            "type": error["type"],
        }
        for error in exc.errors(include_input=False, include_context=False, include_url=False)[:30]
    ]


def normalize_payload(payload):
    if not isinstance(payload, dict):
        return payload
    result = dict(payload)

    def number(value, path, rate=False):
        if not isinstance(value, str) or len(value) > 80:
            return value
        # Only comma-grouped values with an explicit decimal point are unambiguous here.
        # Decimal-comma, currency prefixes, malformed groups and bare percentages elsewhere fail.
        if GROUPED.fullmatch(value):
            logger.info("gemini_value_normalized field=%s operation=remove_grouping", path)
            return value.replace(",", "")
        if rate and PERCENT.fullmatch(value):
            sign, digits, exponent = Decimal(value[:-1]).as_tuple()
            converted = Decimal((sign, digits, exponent - 2))
            logger.info("gemini_value_normalized field=%s operation=percent_to_fraction", path)
            return format(converted, "f")
        return value

    for field in ("subtotal", "tax_amount", "total", "tax_rate"):
        if field in result:
            result[field] = number(result[field], field, field == "tax_rate")
    if isinstance(result.get("line_items"), list):
        items = []
        for index, item in enumerate(result["line_items"]):
            if not isinstance(item, dict):
                items.append(item)
                continue
            item = dict(item)
            for field in ("quantity", "unit_price", "line_total"):
                if field in item:
                    item[field] = number(item[field], f"line_items.{index}.{field}")
            items.append(item)
        result["line_items"] = items
    return result


def parse_response(response):
    candidates = response.candidates or []
    candidate = candidates[0] if candidates else None
    reason = getattr(getattr(candidate, "finish_reason", None), "name", "UNKNOWN")
    # The SDK enum supplies these names; never log arbitrary provider strings.
    safe_reasons = {
        "STOP",
        "MAX_TOKENS",
        "SAFETY",
        "RECITATION",
        "OTHER",
        "BLOCKLIST",
        "PROHIBITED_CONTENT",
        "SPII",
        "MALFORMED_FUNCTION_CALL",
        "UNKNOWN",
    }
    reason = reason if reason in safe_reasons else "OTHER"
    parts = getattr(getattr(candidate, "content", None), "parts", None) or []
    text = "".join(part.text for part in parts if part.text and not part.thought)
    logger.info(
        "gemini_response finish_reason=%s candidates=%s text_chars=%s",
        reason,
        len(candidates),
        len(text),
    )

    def rejected(code):
        logger.warning(
            "gemini_output_rejected code=%s finish_reason=%s text_chars=%s", code, reason, len(text)
        )
        return ExtractionError(code)

    if reason == "MAX_TOKENS":
        raise rejected("GEMINI_RESPONSE_TRUNCATED")
    if reason not in ("STOP", "UNKNOWN"):
        raise rejected("GEMINI_RESPONSE_BLOCKED")
    if not text.strip():
        raise rejected("GEMINI_EMPTY_RESPONSE")
    if reason != "STOP":
        raise rejected("GEMINI_INCOMPLETE_RESPONSE")
    try:
        payload = json.loads(text)
    except (ValueError, TypeError) as exc:
        logger.warning(
            "gemini_output_rejected stage=json type=malformed_json finish_reason=%s", reason
        )
        raise ExtractionError("GEMINI_MALFORMED_JSON") from exc
    payload = normalize_payload(payload)
    try:
        # Validate the wire shape, then the unchanged financial domain model.
        GeminiInvoice.model_validate(payload)
        InvoiceExtraction.model_validate(payload)
    except ValidationError as exc:
        logger.warning(
            "gemini_output_rejected stage=pydantic finish_reason=%s errors=%s",
            reason,
            validation_errors(exc),
        )
        raise ExtractionError("INVALID_EXTRACTION_OUTPUT") from exc
    return parse_extraction(payload)
