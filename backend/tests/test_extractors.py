import json

import httpx
import pytest
from google import genai
from pydantic import SecretStr

from app.modules.extraction.adapters import ExtractionError, MockExtractor
from app.modules.extraction.gemini import GeminiExtractor
from tests.conftest import ROOT


def test_mock_resolves_source_hash_not_filename(tmp_path, clean_pdf):
    renamed = tmp_path / "arbitrary-name.pdf"
    renamed.write_bytes(clean_pdf)
    assert MockExtractor(ROOT / "fixtures").extract(renamed, "application/pdf").total == 1150
    renamed = tmp_path / "clean-001.pdf"
    renamed.write_bytes(clean_pdf + b"\n% changed source bytes\n")
    with pytest.raises(ExtractionError, match="MOCK_FIXTURE_NOT_FOUND"):
        MockExtractor(ROOT / "fixtures").extract(renamed, "application/pdf")


def test_mock_failure_fixture_is_explicit():
    with pytest.raises(ExtractionError, match="MOCK_EXTRACTION_FAILED"):
        MockExtractor(ROOT / "fixtures").extract(
            ROOT / "fixtures/invoices/extraction-failure.pdf", "application/pdf"
        )


def sdk_extractor(settings, handler, sleeps):
    settings.gemini_api_key = SecretStr("offline-test-key")
    settings.gemini_model = "configured-test-model"

    def factory(**kwargs):
        options = kwargs["http_options"]
        options.client_args = {"transport": httpx.MockTransport(handler)}
        return genai.Client(**kwargs)

    return GeminiExtractor(settings, client_factory=factory, sleep=sleeps.append)


def success(payload):
    return httpx.Response(
        200,
        json={
            "candidates": [
                {
                    "content": {"role": "model", "parts": [{"text": json.dumps(payload)}]},
                    "finishReason": "STOP",
                }
            ]
        },
    )


def sample_payload():
    return json.loads((ROOT / "fixtures/answers.json").read_text())["fixtures"]["clean-001.pdf"][
        "extraction"
    ]


def test_real_sdk_wire_contract_and_transient_retry(settings, caplog):
    calls, sleeps = [], []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(
                429, json={"error": {"code": 429, "message": "private-document-text"}}
            )
        return success(sample_payload())

    result = sdk_extractor(settings, handler, sleeps).extract(
        ROOT / "fixtures/invoices/clean-001.pdf", "application/pdf"
    )
    assert str(result.total) == "1150.00"
    assert len(calls) == 2 and len(sleeps) == 1
    wire = json.loads(calls[-1].content)
    assert "specialized financial document" in wire["systemInstruction"]["parts"][0]["text"]
    assert "Never invent" in wire["systemInstruction"]["parts"][0]["text"]
    assert wire["generationConfig"]["responseMimeType"] == "application/json"
    assert wire["generationConfig"]["responseJsonSchema"]["properties"]["invoice_number"]
    assert wire["contents"][0]["parts"][0]["inlineData"]["mimeType"] == "application/pdf"
    assert calls[0].extensions["timeout"]["read"] == 60
    assert "private-document-text" not in caplog.text


@pytest.mark.parametrize("status,expected_calls", [(400, 1), (401, 1), (500, 3), (429, 3)])
def test_sdk_retry_ceiling(settings, status, expected_calls):
    calls, sleeps = [], []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, json={"error": {"code": status, "message": "redacted"}})

    with pytest.raises(ExtractionError, match="GEMINI_API_ERROR"):
        sdk_extractor(settings, handler, sleeps).extract(
            ROOT / "fixtures/invoices/clean-001.pdf", "application/pdf"
        )
    assert len(calls) == expected_calls
    assert len(sleeps) == expected_calls - 1
    assert all(0 <= delay <= 2.2 for delay in sleeps)


@pytest.mark.parametrize(
    "timeout_type,phase",
    [
        (httpx.ConnectTimeout, "connect"),
        (httpx.ReadTimeout, "read"),
        (httpx.WriteTimeout, "write"),
        (httpx.PoolTimeout, "pool"),
    ],
)
def test_sdk_timeout_is_bounded_and_sanitized(settings, caplog, timeout_type, phase, monkeypatch):
    # Alembic's fileConfig disables existing loggers in preceding integration tests.
    from app.modules.extraction.gemini import logger

    monkeypatch.setattr(logger, "disabled", False)
    caplog.set_level("WARNING", logger=logger.name)
    calls, sleeps = [], []

    def handler(request):
        calls.append(request)
        raise timeout_type("private-document-text", request=request)

    with pytest.raises(ExtractionError, match="GEMINI_TIMEOUT"):
        sdk_extractor(settings, handler, sleeps).extract(
            ROOT / "fixtures/invoices/clean-001.pdf", "application/pdf"
        )
    assert len(calls) == 3
    assert f"timeout_phase={phase}" in caplog.text
    assert "private-document-text" not in caplog.text


def test_sdk_invalid_response_is_not_retried(settings):
    calls, sleeps = [], []

    def handler(request):
        calls.append(request)
        return success({"total": 1.15})

    with pytest.raises(ExtractionError, match="INVALID_EXTRACTION_OUTPUT"):
        sdk_extractor(settings, handler, sleeps).extract(
            ROOT / "fixtures/invoices/clean-001.pdf", "application/pdf"
        )
    assert len(calls) == 1 and sleeps == []


def test_gemini_missing_credentials_fails_before_network(settings):
    with pytest.raises(ExtractionError, match="GEMINI_NOT_CONFIGURED"):
        GeminiExtractor(settings).extract(
            ROOT / "fixtures/invoices/clean-001.pdf", "application/pdf"
        )
