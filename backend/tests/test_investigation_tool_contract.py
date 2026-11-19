"""Schema-constrained Gemini declarations never replace the host's hard gate."""

import json
import uuid
from types import SimpleNamespace

import httpx
import pytest
from google import genai
from google.genai import types

from app.modules.investigation.gemini_provider import GeminiInvestigationProvider, initial_history
from app.modules.investigation.live_graph import build_live_graph
from app.modules.investigation.mcp_adapter import TOOL_DESCRIPTIONS
from tests.test_investigation import snapshot
from tests.test_investigation_live import FakeGemini


def definitions():
    return [
        {
            "name": name,
            "description": description,
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        }
        for name, description in TOOL_DESCRIPTIONS.items()
    ]


def test_gemini_uses_validated_declared_function_names_and_exact_empty_schema():
    captured = {}

    def generate_content(**kwargs):
        captured.update(kwargs)
        return types.GenerateContentResponse(
            candidates=[
                types.Candidate(
                    content=types.Content(
                        role="model", parts=[types.Part(text="Evidence gathered.")]
                    ),
                    finish_reason="STOP",
                )
            ]
        )

    provider = GeminiInvestigationProvider(
        api_key="synthetic-no-network",
        model="synthetic-model",
        client=SimpleNamespace(models=SimpleNamespace(generate_content=generate_content)),
    )
    declared = definitions()
    turn = provider.step(
        initial_history(["TOTAL_MISMATCH"], ["get_rule_results"]),
        declared,
        timeout_seconds=10,
        max_output_tokens=256,
    )
    assert not turn.calls  # VALIDATED must allow natural termination; ANY would not.
    config = captured["config"]
    calling = config.tool_config.function_calling_config
    assert calling.mode == types.FunctionCallingConfigMode.VALIDATED
    assert calling.allowed_function_names == list(TOOL_DESCRIPTIONS)
    assert config.automatic_function_calling.disable is True
    assert all(
        d.parameters_json_schema
        == {"type": "object", "properties": {}, "additionalProperties": False}
        for d in config.tools[0].function_declarations
    )
    assert "exactly the empty JSON object {}" in config.system_instruction
    assert all("exactly {}" in d.description for d in config.tools[0].function_declarations)


class Budget:
    def call(self, kind, payload, operation, authorize, estimator=None):
        authorize()
        return operation(10, 256)

    def tool(self, name):
        pass


def test_nonempty_arguments_still_hard_deny_without_logging_values(caplog, monkeypatch):
    import logging

    logger = logging.getLogger("app.modules.investigation.live_graph")
    # Alembic's in-process test fixture disables existing loggers. Restore this
    # test's capture boundary just as the existing extraction log tests do.
    monkeypatch.setattr(logger, "disabled", False)
    caplog.set_level("WARNING", logger=logger.name)
    calls = []

    class MCP:
        definitions = definitions()

        def call(self, name, args):
            calls.append((name, args))
            pytest.fail("Forbidden arguments must never cross MCP")

    graph = build_live_graph(FakeGemini(unsafe_args=True), MCP(), Budget(), lambda: None)
    with pytest.raises(ValueError, match="MODEL_TOOL_NOT_ALLOWED"):
        graph.invoke({"snapshot": snapshot(), "run_id": uuid.uuid4()})
    assert not calls
    assert "tool=get_rule_results nonempty_arguments=True" in caplog.text
    assert "forbidden" not in caplog.text
    assert "invoice_id" not in caplog.text


def test_pinned_sdk_serializes_validated_zero_argument_contract_on_wire():
    captured = {}

    def transport(request):
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {"role": "model", "parts": [{"text": "Evidence gathered."}]},
                        "finishReason": "STOP",
                    }
                ],
            },
        )

    http = httpx.Client(transport=httpx.MockTransport(transport))
    client = genai.Client(
        api_key="synthetic-no-network",
        http_options=types.HttpOptions(
            httpx_client=http,
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )
    provider = GeminiInvestigationProvider(
        api_key="synthetic-no-network", model="synthetic-model", client=client
    )
    try:
        provider.step(
            initial_history(["TOTAL_MISMATCH"], ["get_rule_results"]),
            definitions(),
            timeout_seconds=10,
            max_output_tokens=256,
        )
    finally:
        provider.close()
        http.close()
    assert captured["toolConfig"]["functionCallingConfig"] == {
        "mode": "VALIDATED",
        "allowedFunctionNames": list(TOOL_DESCRIPTIONS),
    }
    declarations = captured["tools"][0]["functionDeclarations"]
    assert all(
        d.get("parametersJsonSchema", d.get("parameters_json_schema"))
        == {"type": "object", "properties": {}, "additionalProperties": False}
        for d in declarations
    )
