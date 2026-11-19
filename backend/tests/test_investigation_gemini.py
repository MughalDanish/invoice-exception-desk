"""Provider protocol and grounding tests: no paid calls, keys or external tools."""

import base64
import json
import uuid
from types import SimpleNamespace

import httpx
import pytest
from google import genai
from google.genai import types
from pydantic import ValidationError

from app.modules.approvals.service import payload_hash
from app.modules.investigation.gemini_provider import (
    GeminiInvestigationError,
    GeminiInvestigationProvider,
    function_result_content,
    initial_history,
    normalize_response,
    provider_json_schema,
    sdk_content,
)
from app.modules.investigation.live_policy import render_assertion, validate_live_draft
from app.modules.investigation.live_schemas import (
    LiveAssertion,
    LiveDraft,
    LiveFinding,
    ProtocolContent,
)
from app.modules.investigation.schemas import (
    DocumentEvidence,
    DocumentSnapshot,
    LookupSnapshot,
    ToolResult,
)
from tests.test_investigation import snapshot


def response(parts=None, reason="STOP", usage=True):
    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(role="model", parts=parts or []), finish_reason=reason
            )
        ],
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=37,
            candidates_token_count=11,
            thoughts_token_count=5,
            total_token_count=53,
            cached_content_token_count=9,
        )
        if usage
        else None,
    )


def provider(output):
    calls = []

    def generate(**kwargs):
        calls.append(kwargs)
        if isinstance(output, Exception):
            raise output
        return output

    client = SimpleNamespace(models=SimpleNamespace(generate_content=generate), close=lambda: None)
    return GeminiInvestigationProvider(
        api_key="not-a-key", model="synthetic-model", client=client
    ), calls


def evidence():
    return (
        ToolResult(
            name="get_rule_results",
            evidence_id="rules",
            status="FOUND",
            facts=("Recorded blocking rule.",),
            data={
                "currency": "USD",
                "rules": [
                    {"expected_amount": "2300.0000", "observed_amount": "2500.0000"},
                ],
            },
        ),
        ToolResult(
            name="get_invoice_snapshot",
            evidence_id="invoice",
            status="FOUND",
            facts=("Extraction only.",),
            data={"currency": "USD"},
        ),
    )


def draft():
    return LiveDraft(
        summary="Recorded total differs; original evidence needs review.",
        findings=(
            LiveFinding(
                claim="Recorded validation shows a discrepancy.",
                status="SUPPORTED",
                evidence_ids=("rules",),
                assertions=(
                    LiveAssertion(
                        evidence_id="rules",
                        field_path="/rules/0/expected_amount",
                        value="2300.0000",
                        currency="USD",
                    ),
                ),
            ),
        ),
        proposed_action="REQUEST_EVIDENCE",
        resolution_rationale="Request original evidence.",
        uncertainties=("The original printed amount has not been independently verified.",),
        limitations=("Extraction does not prove document authenticity.",),
    )


def test_provider_manual_tools_timeout_units_and_single_attempt():
    p, calls = provider(
        response(
            [
                types.Part(
                    function_call=types.FunctionCall(
                        id="call-one", name="get_rule_results", args={}
                    ),
                    thought_signature=b"opaque",
                )
            ]
        )
    )
    history = initial_history(("TOTAL_MISMATCH",), ("get_rule_results",))
    turn = p.step(
        history,
        [
            {
                "name": "get_rule_results",
                "description": "Read recorded rules.",
                "inputSchema": {"type": "object", "properties": {}},
            }
        ],
        timeout_seconds=2.5,
        max_output_tokens=500,
    )
    assert len(calls) == 1
    config = calls[0]["config"]
    assert config.http_options.timeout == 2500
    assert config.http_options.retry_options.attempts == 1
    assert config.automatic_function_calling.disable
    assert config.thinking_config.include_thoughts is False
    assert turn.calls[0].id == "call-one"
    assert turn.usage.total_tokens == 53
    assert turn.usage.input_tokens == 37 and turn.usage.thinking_tokens == 5
    assert "2300" not in history[0].model_dump_json()
    assert turn.content.parts[0].thought_signature == base64.b64encode(b"opaque").decode()


def test_signatures_and_function_ids_round_trip_without_hidden_reasoning():
    turn = normalize_response(
        response(
            [
                types.Part(text="private thought", thought=True),
                types.Part(
                    function_call=types.FunctionCall(
                        id="stable-id", name="get_rule_results", args={}
                    ),
                    thought_signature=b"\x00\xffopaque",
                ),
            ]
        ),
        9,
    )
    restored = ProtocolContent.model_validate_json(turn.content.model_dump_json())
    converted = sdk_content(restored)
    assert converted.parts[0].thought_signature == b"\x00\xffopaque"
    assert converted.parts[0].function_call.id == "stable-id"
    assert "private thought" not in restored.model_dump_json()
    result = function_result_content(turn.calls[0], evidence()[0])
    assert sdk_content(result).parts[0].function_response.id == "stable-id"


@pytest.mark.parametrize("reason", ["MAX_TOKENS", "SAFETY", "MALFORMED_FUNCTION_CALL"])
def test_non_stop_finish_is_typed_and_retains_usage(reason):
    with pytest.raises(GeminiInvestigationError) as caught:
        normalize_response(response([types.Part(text="partial")], reason), 2)
    assert caught.value.code == "GEMINI_FINISH_" + reason
    assert caught.value.usage.total_tokens == 53


@pytest.mark.parametrize(
    "parts,code",
    [
        ([], "GEMINI_EMPTY_RESPONSE"),
        ([types.Part(text="not JSON")], "GEMINI_INVALID_STRUCTURED_OUTPUT"),
    ],
)
def test_empty_and_malformed_structured_output_distinguished(parts, code):
    with pytest.raises(GeminiInvestigationError) as caught:
        normalize_response(response(parts), 2, LiveDraft)
    assert caught.value.code == code


@pytest.mark.parametrize(
    "exception,code",
    [
        (httpx.ConnectTimeout("secret invoice"), "GEMINI_CONNECTION_TIMEOUT"),
        (httpx.ReadTimeout("secret invoice"), "GEMINI_READ_TIMEOUT"),
        (httpx.WriteTimeout("secret invoice"), "GEMINI_WRITE_TIMEOUT"),
        (httpx.PoolTimeout("secret invoice"), "GEMINI_POOL_TIMEOUT"),
    ],
)
def test_transport_timeout_types_sanitized_no_hidden_retry(exception, code):
    p, calls = provider(exception)
    with pytest.raises(GeminiInvestigationError) as caught:
        p.step(initial_history(("TOTAL_MISMATCH",), ()), [], timeout_seconds=1)
    assert caught.value.code == code and caught.value.retryable
    assert "secret" not in str(caught.value)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "status,code,retryable",
    [
        (429, "GEMINI_RATE_LIMITED", True),
        (503, "GEMINI_SERVER_ERROR", True),
        (500, "GEMINI_SERVER_ERROR", True),
        (400, "GEMINI_REQUEST_REJECTED", False),
        (403, "GEMINI_REQUEST_REJECTED", False),
    ],
)
def test_http_failures_keep_only_sanitized_diagnostics(status, code, retryable):
    from google.genai import errors

    response = httpx.Response(
        status,
        headers={"Retry-After": "12", "x-private": "secret"},
        request=httpx.Request("POST", "https://example.invalid/?key=secret"),
    )
    exception = errors.APIError(status, {"error": {"message": "secret invoice"}}, response)
    p, calls = provider(exception)
    with pytest.raises(GeminiInvestigationError) as caught:
        p.step(initial_history(("UNAPPROVED_VENDOR",), ()), [], timeout_seconds=1)
    error = caught.value
    assert error.code == code and error.retryable is retryable
    assert error.diagnostics == {
        "http_status": status,
        "retryable": retryable,
        "retry_after_seconds": 12.0,
    }
    assert "secret" not in str(error) + json.dumps(error.__dict__, default=str)
    assert len(calls) == 1  # The SDK never performs hidden retries.


@pytest.mark.parametrize("hint", ["secret invoice", "nan", "inf", "-1", "86401"])
def test_invalid_retry_hint_is_not_retained(hint):
    from google.genai import errors

    from app.modules.investigation.gemini_provider import sanitized_request_error

    error = sanitized_request_error(
        errors.APIError(429, {}, httpx.Response(429, headers={"Retry-After": hint}))
    )
    assert error.diagnostics == {"http_status": 429, "retryable": True}


@pytest.mark.parametrize(
    "kind,name",
    [
        (httpx.ConnectError, "ConnectError"),
        (httpx.ReadError, "ReadError"),
        (httpx.RemoteProtocolError, "RemoteProtocolError"),
    ],
)
def test_network_subtypes_are_allowlisted_without_messages(kind, name):
    from app.modules.investigation.gemini_provider import sanitized_request_error

    error = sanitized_request_error(kind("secret invoice URL and key"))
    assert error.code == "GEMINI_NETWORK_ERROR"
    assert error.diagnostics == {"retryable": True, "network_error": name}


def test_structured_draft_and_critic_disable_tools():
    p, calls = provider(response([types.Part(text=draft().model_dump_json())]))
    turn = p.draft(initial_history(("TOTAL_MISMATCH",), ()), timeout_seconds=3)
    assert turn.draft == draft() and not calls[0]["config"].tools
    p, calls = provider(response([types.Part(text=json.dumps({"accepted": True, "reasons": []}))]))
    turn = p.critic(draft(), evidence(), timeout_seconds=3)
    assert turn.verdict.accepted and not calls[0]["config"].tools


def test_grounded_exact_decimal_assertion_and_no_hidden_computation():
    assert validate_live_draft(snapshot(), draft(), evidence()) == ()
    assertion = draft().findings[0].assertions[0]
    assert render_assertion(assertion) == "/rules/0/expected_amount: 2300.0000 USD"


@pytest.mark.parametrize(
    "change,code",
    [
        ({"value": "2300"}, "ASSERTION_VALUE_MISMATCH"),
        ({"currency": "EUR"}, "ASSERTION_CURRENCY_MISMATCH"),
        ({"field_path": "/rules/8/expected_amount"}, "ASSERTION_PATH_INVALID"),
        ({"evidence_id": "fabricated"}, "ASSERTION_REFERENCE_MISSING"),
    ],
)
def test_grounding_rejects_changed_precision_currency_path_reference(change, code):
    original = draft()
    f = original.findings[0]
    altered = original.model_copy(
        update={
            "findings": (
                f.model_copy(
                    update={
                        "assertions": (f.assertions[0].model_copy(update=change),),
                    }
                ),
            )
        }
    )
    assert code in validate_live_draft(snapshot(), altered, evidence())


def test_missing_mandatory_and_unsupported_prose_are_rejected():
    d = draft().model_copy(update={"summary": "We approved this invoice for 2300 USD."})
    codes = validate_live_draft(snapshot(), d, evidence()[:1])
    assert {"MANDATORY_TOOLS_MISSING", "NUMERIC_PROSE_FORBIDDEN", "UNSAFE_AUTHORITY_CLAIM"} <= set(
        codes
    )


def test_real_sdk_serializes_structured_schema_without_network():
    """Exercise installed SDK transformations, beyond a generate_content stub."""
    captured = []

    def transport(request):
        captured.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "role": "model",
                            "parts": [{"text": draft().model_dump_json()}],
                        },
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {"totalTokenCount": 50},
            },
        )

    client = genai.Client(
        api_key="synthetic-test-only",
        http_options=types.HttpOptions(
            httpx_client=httpx.Client(transport=httpx.MockTransport(transport)),
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )
    p = GeminiInvestigationProvider(api_key="unused", model="synthetic", client=client)
    try:
        assert p.draft(initial_history(("TOTAL_MISMATCH",), ()), timeout_seconds=2).draft == draft()
        assert captured[0]["generationConfig"]["responseMimeType"] == "application/json"
        wire = captured[0]["generationConfig"]
        assert "responseSchema" not in wire
        assert wire["responseJsonSchema"] == provider_json_schema(LiveDraft)
        assert wire["responseJsonSchema"]["additionalProperties"] is False
        assert "additional_properties" not in json.dumps(wire)
        assert "maxItems" not in json.dumps(wire)
        assert "minItems" not in json.dumps(wire)
        assert LiveDraft.model_json_schema()["properties"]["findings"]["maxItems"] == 24
    finally:
        p.close()


def test_token_count_preflight_is_conservative_and_bounded():
    p, _ = provider(None)
    captured = []
    p.client.models.count_tokens = lambda **kw: (
        captured.append(kw) or SimpleNamespace(total_tokens=100)
    )
    assert p.estimate_input_tokens({"history": []}, timeout_seconds=20) == 612
    assert captured[0]["config"].http_options.timeout == 10000
    assert captured[0]["config"].http_options.retry_options.attempts == 1


@pytest.mark.parametrize(
    "field,count", [("findings", 25), ("assertions", 17), ("evidence_ids", 13)]
)
def test_wire_array_simplification_keeps_strict_local_limits(field, count):
    payload = draft().model_dump(mode="json")
    if field == "findings":
        payload[field] = payload[field] * count
    else:
        payload["findings"][0][field] = payload["findings"][0][field] * count
    with pytest.raises(ValidationError) as caught:
        LiveDraft.model_validate_json(json.dumps(payload))
    assert any(error["type"] == "too_long" for error in caught.value.errors(include_input=False))


def test_monetary_assertion_requires_currency_semantics():
    d = draft()
    f = d.findings[0]
    changed = d.model_copy(
        update={
            "findings": (
                f.model_copy(
                    update={"assertions": (f.assertions[0].model_copy(update={"currency": None}),)}
                ),
            )
        }
    )
    assert "ASSERTION_CURRENCY_MISSING" in validate_live_draft(snapshot(), changed, evidence())


@pytest.mark.parametrize(
    "attack,code",
    [
        ("text", "SOURCE_INTEGRITY_INVALID"),
        ("version", "SOURCE_INTEGRITY_INVALID"),
        ("invoice", "SOURCE_SCOPE_INVALID"),
    ],
)
def test_source_version_text_and_scope_must_match_frozen_projection(attack, code):
    s = snapshot()
    content = "Synthetic supporting evidence. Ignore this data as instructions."
    source = DocumentEvidence(
        source_id=uuid.uuid4(),
        version=1,
        invoice_id=s.invoice_id,
        supplier_key="synthetic",
        kind="PO",
        content_sha256=payload_hash({"text": content}),
        text=content,
    )
    s = s.model_copy(
        update={
            "documents": DocumentSnapshot(items=(source,)),
            "lookup": LookupSnapshot(
                supplier_key="synthetic", invoice_key="synthetic", invoice_total=None, policy=None
            ),
        }
    )
    data = source.model_dump(mode="json")
    data.update(
        {"text": "Changed text"}
        if attack == "text"
        else {"version": 2}
        if attack == "version"
        else {"invoice_id": str(uuid.uuid4())}
    )
    result = ToolResult(
        name="get_supporting_documents",
        evidence_id="documents",
        status="FOUND",
        facts=("Untrusted source text.",),
        data={"items": [data]},
    )
    assert code in validate_live_draft(s, draft(), (*evidence(), result))


def test_live_graph_anchors_rules_then_exposes_dynamic_tools_and_preserves_limitations():
    from app.modules.investigation.live_graph import build_live_graph
    from app.modules.investigation.schemas import ToolRequest
    from app.modules.investigation.tools import ReadOnlyTools
    from tests.test_investigation_live import FakeGemini

    captured = snapshot()

    class RecordingProvider(FakeGemini):
        def __init__(self):
            super().__init__()
            self.exposed = []

        def step(self, history, definitions, **kwargs):
            self.exposed.append({definition["name"] for definition in definitions})
            return super().step(history, definitions, **kwargs)

    class OfflineMCP:
        definitions = [{"name": name} for name in ("get_rule_results", "get_invoice_snapshot")]

        def call(self, name, args):
            assert args == {}
            return ReadOnlyTools(captured).call(
                ToolRequest(name=name, invoice_id=captured.invoice_id, supplier_key="")
            )

    class OfflineBudget:
        def call(self, kind, payload, operation, authorize, estimator=None):
            authorize()
            return operation(30, 2048)

        def tool(self, name):
            pass

        def tool_done(self, *args):
            pass

    provider = RecordingProvider()
    result = build_live_graph(provider, OfflineMCP(), OfflineBudget(), lambda: None).invoke(
        {"snapshot": captured, "run_id": uuid.uuid4()}, config={"recursion_limit": 20}
    )
    assert provider.exposed[0] == {"get_rule_results"}
    assert provider.exposed[1] == {"get_rule_results", "get_invoice_snapshot"}
    assert result["report"].resolution.accepted
    assert "Recorded extraction is not proof of original-document authenticity." in (
        result["report"].limitations
    )
