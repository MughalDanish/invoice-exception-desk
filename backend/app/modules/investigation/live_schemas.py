"""Closed local protocol state and advisory outputs; never persist SDK objects."""

from typing import Annotated, Any, Literal

from pydantic import Field

from app.modules.investigation.schemas import Action, Contract, Text


class ModelToolCall(Contract):
    id: Annotated[str, Field(max_length=200)] | None = None
    name: Annotated[str, Field(min_length=1, max_length=100)]
    args: dict[str, Any] = Field(default_factory=dict)


class ProtocolPart(Contract):
    text: Annotated[str, Field(max_length=24000)] | None = None
    function_call: ModelToolCall | None = None
    function_response: dict[str, Any] | None = None
    thought_signature: Annotated[str, Field(max_length=64000)] | None = None


class ProtocolContent(Contract):
    role: Literal["user", "model"]
    parts: Annotated[tuple[ProtocolPart, ...], Field(min_length=1, max_length=16)]


class TokenUsage(Contract):
    input_tokens: Annotated[int, Field(ge=0)] | None = None
    output_tokens: Annotated[int, Field(ge=0)] | None = None
    thinking_tokens: Annotated[int, Field(ge=0)] | None = None
    cached_tokens: Annotated[int, Field(ge=0)] | None = None
    total_tokens: Annotated[int, Field(ge=0)] | None = None


class LiveAssertion(Contract):
    evidence_id: Annotated[str, Field(min_length=1, max_length=180)]
    field_path: Annotated[str, Field(pattern=r"^/", max_length=250)]
    value: Annotated[str, Field(max_length=1000)] | bool | None
    currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")] | None = None


class LiveFinding(Contract):
    claim: Text
    status: Literal["SUPPORTED", "CONTRADICTED", "INSUFFICIENT", "HYPOTHESIS"]
    evidence_ids: Annotated[tuple[str, ...], Field(min_length=1, max_length=12)]
    assertions: Annotated[tuple[LiveAssertion, ...], Field(max_length=16)] = ()


class LiveDraft(Contract):
    summary: Text
    findings: Annotated[tuple[LiveFinding, ...], Field(min_length=1, max_length=24)]
    proposed_action: Action
    resolution_rationale: Text
    uncertainties: Annotated[tuple[Text, ...], Field(min_length=1, max_length=24)]
    limitations: Annotated[tuple[Text, ...], Field(min_length=1, max_length=8)]


class LiveCritic(Contract):
    accepted: bool
    reasons: Annotated[tuple[Text, ...], Field(max_length=8)] = ()


class ModelTurn(Contract):
    content: ProtocolContent | None = None
    calls: Annotated[tuple[ModelToolCall, ...], Field(max_length=12)] = ()
    usage: TokenUsage = Field(default_factory=TokenUsage)
    finish_reason: Annotated[str, Field(max_length=80)] = "UNKNOWN"
    latency_ms: Annotated[int, Field(ge=0)] = 0
    draft: LiveDraft | None = None
    verdict: LiveCritic | None = None
