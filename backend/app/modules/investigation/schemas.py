"""Strict, bounded contracts. Amounts remain exact strings, never floats."""

import re
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Text = Annotated[str, Field(min_length=1, max_length=1200)]
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Amount = Annotated[str, Field(pattern=r"^-?\d{1,32}(?:\.\d{1,16})?$", max_length=50)]
Action = Literal[
    "REQUEST_CORRECTED_INVOICE",
    "REQUEST_EVIDENCE",
    "REVIEW_DUPLICATE",
    "REVIEW_SUPPLIER",
    "REVIEW_POLICY",
    "NO_RECOMMENDATION",
]
RunStatus = Literal["RUNNING", "COMPLETED", "FAILED", "STALE"]


class Contract(BaseModel):
    model_config = ConfigDict(
        strict=True,
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class RuleEvidence(Contract):
    id: UUID
    code: Annotated[str, Field(min_length=1, max_length=80)]
    expected_amount: Amount | None = None
    observed_amount: Amount | None = None


class SupplierPolicy(Contract):
    id: UUID
    approved: bool
    currency: str | None
    amount_limit: Amount | None


class DuplicateCandidate(Contract):
    id: UUID
    revision: Annotated[int, Field(ge=1)]
    status: str
    payload_hash: Digest


class LedgerFact(Contract):
    id: UUID
    currency: str
    total: Amount


class LookupSnapshot(Contract):
    supplier_key: Annotated[str, Field(max_length=200)]
    invoice_key: Annotated[str, Field(max_length=200)]
    invoice_total: Amount | None
    policy: SupplierPolicy | None
    duplicates: Annotated[tuple[DuplicateCandidate, ...], Field(max_length=20)] = ()
    ledger_matches: Annotated[tuple[LedgerFact, ...], Field(max_length=20)] = ()
    history: Annotated[tuple[LedgerFact, ...], Field(max_length=20)] = ()
    duplicates_truncated: bool = False
    ledger_matches_truncated: bool = False
    history_truncated: bool = False


Role = Literal["financial", "supplier"]
TaskKind = Literal["arithmetic", "duplicate", "supplier", "outlier", "unsupported"]
ToolName = Literal[
    "get_invoice_snapshot",
    "get_rule_results",
    "find_duplicate_candidates",
    "get_supplier_policy",
    "get_supplier_history",
]


class PlanTask(Contract):
    task_id: Annotated[str, Field(min_length=1, max_length=100)]
    rule_id: UUID
    role: Role
    kind: TaskKind
    tools: Annotated[tuple[ToolName, ...], Field(min_length=1, max_length=3)]


class InvestigationPlan(Contract):
    tasks: Annotated[tuple[PlanTask, ...], Field(min_length=1, max_length=64)]


class ToolRequest(Contract):
    name: ToolName
    invoice_id: UUID
    supplier_key: Annotated[str, Field(max_length=200)]


class ToolResult(Contract):
    name: ToolName
    evidence_id: Annotated[str, Field(min_length=1, max_length=180)]
    status: Literal["FOUND", "MISSING", "NOT_READ"]
    facts: Annotated[tuple[Text, ...], Field(min_length=1, max_length=4)]


class InvoiceSnapshot(Contract):
    invoice_id: UUID
    revision: Annotated[int, Field(ge=1)]
    payload_sha256: Digest
    validation_batch_id: UUID
    document_sha256: Digest
    currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")] | None
    blockers: Annotated[tuple[RuleEvidence, ...], Field(min_length=1, max_length=64)]
    lookup: LookupSnapshot | None = None


class Finding(Contract):
    task_id: Annotated[str, Field(min_length=1, max_length=100)]
    claim: Text
    evidence_ids: Annotated[tuple[str, ...], Field(min_length=1, max_length=4)]
    status: Literal["SUPPORTED", "CONTRADICTED", "INSUFFICIENT"]


class Findings(Contract):
    items: Annotated[tuple[Finding, ...], Field(min_length=1, max_length=64)]


class InvestigationReport(Contract):
    summary: Text
    findings: Annotated[tuple[Finding, ...], Field(min_length=1, max_length=64)]
    proposed_action: Action
    missing_evidence: Annotated[tuple[Text, ...], Field(max_length=64)]
    limitations: Annotated[tuple[Text, ...], Field(min_length=1, max_length=8)]
    source_revision: Annotated[int, Field(ge=1)]
    source_payload_hash: Digest
    source_validation_batch: UUID
    mode: Literal["mock"] = "mock"
    advisory_only: Literal[True] = True
    plan: InvestigationPlan | None = None
    tools_used: Annotated[tuple[ToolName, ...], Field(max_length=12)] = ()
    lookup_digest: Digest | None = None


class InvestigationRequest(Contract):
    expected_revision: Annotated[int, Field(ge=1)]
    idempotency_key: Annotated[str, Field(min_length=1, max_length=100, pattern=r"^[\w.-]+$")]


class InvestigationView(Contract):
    run_id: UUID
    invoice_id: UUID
    status: RunStatus
    applicable: bool
    mode: Literal["mock"]
    execution: Literal["synchronous_local"] = "synchronous_local"
    created_at: datetime
    report: InvestigationReport | None
    error_code: str | None


def exact_amount(value: object) -> str | None:
    """Missing or malformed recorded evidence stays missing; no repair or inference."""
    if not isinstance(value, str) or not re.fullmatch(r"-?\d{1,32}(?:\.\d{1,16})?", value):
        return None
    return value if len(value) <= 50 and Decimal(value).is_finite() else None
