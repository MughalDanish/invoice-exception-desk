"""Small fixed graph: snapshot -> findings -> guarded advisory report.

No supervisor, retrieval, network, checkpoint or financial tool exists in Day 6.
"""

from typing import Annotated, TypedDict
from uuid import UUID

from langgraph.graph import END, START, StateGraph

from app.modules.investigation.providers import InvestigationProvider, expected_finding
from app.modules.investigation.schemas import (
    Finding,
    Findings,
    InvestigationReport,
    InvoiceSnapshot,
)


def merge_findings(left: dict[str, Finding], right: dict[str, Finding]) -> dict[str, Finding]:
    """Stable IDs make merging bounded and deterministic; conflicts fail closed."""
    merged = dict(left)
    for key, finding in right.items():
        if key != finding.task_id or (key in merged and merged[key] != finding):
            raise ValueError("Conflicting investigation finding")
        merged[key] = finding
    if len(merged) > 64:
        raise ValueError("Too many investigation findings")
    return dict(sorted(merged.items()))


class InvestigationState(TypedDict):
    run_id: UUID
    snapshot: InvoiceSnapshot
    findings: Annotated[dict[str, Finding], merge_findings]
    report: InvestigationReport


def build_graph(provider: InvestigationProvider):
    def capture(state: InvestigationState):
        # Frozen Pydantic contracts are the runtime boundary; TypedDict alone is not validation.
        snapshot = InvoiceSnapshot.model_validate(state["snapshot"])
        return {"snapshot": snapshot}

    def investigate(state: InvestigationState):
        bundle = Findings.model_validate(provider.investigate(state["snapshot"]))
        findings = {finding.task_id: finding for finding in bundle.items}
        if len(findings) != len(bundle.items):
            raise ValueError("Duplicate task result")
        return {"findings": findings}

    def report(state: InvestigationState):
        snapshot = state["snapshot"]
        # The minimal provider has one allowlisted output per blocker. Unknown citations,
        # altered numeric claims, omissions and unsupported actions never reach storage.
        expected = {str(r.id): expected_finding(snapshot, r) for r in snapshot.blockers}
        if state["findings"] != expected:
            raise ValueError("Unsupported investigation output")
        findings = tuple(state["findings"].values())
        result = InvestigationReport(
            summary="Mock advisory investigation of the current validation exceptions.",
            findings=findings,
            proposed_action="REQUEST_EVIDENCE",
            missing_evidence=(
                "Human verification of the original document; no document was read by this graph.",
            ),
            limitations=(
                "Scripted mock output, not live AI reasoning or proof of authenticity.",
                "Only recorded total-mismatch evidence is explained in this milestone.",
                "Human authorization and fresh deterministic validation remain required.",
            ),
            source_revision=snapshot.revision,
            source_payload_hash=snapshot.payload_sha256,
            source_validation_batch=snapshot.validation_batch_id,
        )
        return {"report": result}

    return (
        StateGraph(InvestigationState)
        .add_node("capture_snapshot", capture)
        .add_node("investigate", investigate)
        .add_node("advisory_report", report)
        .add_edge(START, "capture_snapshot")
        .add_edge("capture_snapshot", "investigate")
        .add_edge("investigate", "advisory_report")
        .add_edge("advisory_report", END)
        .compile()
    )
