"""Day 7: validated supervisor plan and sequential, dynamically routed workers."""

from typing import Annotated, TypedDict
from uuid import UUID

from langgraph.graph import END, START, StateGraph

from app.modules.approvals.service import payload_hash
from app.modules.investigation.providers import InvestigationProvider, expected_finding
from app.modules.investigation.routing import validate_plan
from app.modules.investigation.schemas import (
    Finding,
    InvestigationPlan,
    InvestigationReport,
    InvoiceSnapshot,
    ToolRequest,
    ToolResult,
)
from app.modules.investigation.tools import ReadOnlyTools


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
    plan: InvestigationPlan
    completed_roles: tuple[str, ...]
    tool_results: dict[str, ToolResult]


def build_graph(provider: InvestigationProvider):
    def capture(state: InvestigationState):
        # Frozen Pydantic contracts are the runtime boundary; TypedDict alone is not validation.
        snapshot = InvoiceSnapshot.model_validate(state["snapshot"])
        return {"snapshot": snapshot}

    def supervise(state: InvestigationState):
        if not hasattr(provider, "plan"):
            raise ValueError("Investigation provider must supply a plan")
        plan = validate_plan(state["snapshot"], provider.plan(state["snapshot"]))
        return {"plan": plan, "completed_roles": (), "tool_results": {}}

    def dispatch(state: InvestigationState):
        return {}

    def next_role(state: InvestigationState):
        for task in state["plan"].tasks:
            if task.role not in state["completed_roles"]:
                return task.role
        return "report"

    def worker(role):
        def execute(state: InvestigationState):
            s = state["snapshot"]
            cache = dict(state["tool_results"])
            findings = {}
            box = ReadOnlyTools(s)
            for task in state["plan"].tasks:
                if task.role != role:
                    continue
                for name in task.tools:
                    if name not in cache:
                        if len(cache) >= 12:
                            raise ValueError("Investigation tool budget exceeded")
                        cache[name] = box.call(
                            ToolRequest(
                                name=name,
                                invoice_id=s.invoice_id,
                                supplier_key=s.lookup.supplier_key if s.lookup else "",
                            )
                        )
                evidence = tuple(cache[name] for name in task.tools)
                finding = Finding.model_validate(provider.investigate(s, task, evidence))
                rule = next(r for r in s.blockers if r.id == task.rule_id)
                if finding != expected_finding(s, rule, evidence):
                    raise ValueError("Unsupported investigation output")
                findings[task.task_id] = finding
            return {
                "findings": findings,
                "tool_results": cache,
                "completed_roles": state["completed_roles"] + (role,),
            }

        return execute

    def report(state: InvestigationState):
        snapshot = state["snapshot"]
        # The minimal provider has one allowlisted output per blocker. Unknown citations,
        # altered numeric claims, omissions and unsupported actions never reach storage.
        expected = {str(r.id): expected_finding(snapshot, r) for r in snapshot.blockers}
        if state["findings"] != expected:
            raise ValueError("Unsupported investigation output")
        findings = tuple(state["findings"].values())
        result = InvestigationReport(
            summary="Mock supervisor investigation of current validation exceptions.",
            findings=findings,
            proposed_action="REQUEST_EVIDENCE",
            missing_evidence=(
                "Human verification of the original document; no document was read by this graph.",
            ),
            limitations=(
                "Scripted mock output, not live AI reasoning or proof of authenticity.",
                "Scoped exact lookups are bounded evidence, not proof of authenticity.",
                "Human authorization and fresh deterministic validation remain required.",
            ),
            plan=state["plan"],
            tools_used=tuple(sorted(state["tool_results"])),
            lookup_digest=payload_hash(snapshot.lookup.model_dump(mode="json"))
            if snapshot.lookup
            else None,
            source_revision=snapshot.revision,
            source_payload_hash=snapshot.payload_sha256,
            source_validation_batch=snapshot.validation_batch_id,
        )
        return {"report": result}

    return (
        StateGraph(InvestigationState)
        .add_node("capture_snapshot", capture)
        .add_node("supervisor", supervise)
        .add_node("dispatch", dispatch)
        .add_node("financial", worker("financial"))
        .add_node("supplier", worker("supplier"))
        .add_node("advisory_report", report)
        .add_edge(START, "capture_snapshot")
        .add_edge("capture_snapshot", "supervisor")
        .add_edge("supervisor", "dispatch")
        .add_conditional_edges(
            "dispatch",
            next_role,
            {
                "financial": "financial",
                "supplier": "supplier",
                "report": "advisory_report",
            },
        )
        .add_edge("financial", "dispatch")
        .add_edge("supplier", "dispatch")
        .add_edge("advisory_report", END)
        .compile()
    )
