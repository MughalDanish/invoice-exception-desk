"""Parallel frozen-read investigators followed by a bounded writer/critic loop."""

from typing import Annotated, TypedDict
from uuid import UUID

from langgraph.graph import END, START, StateGraph

from app.modules.approvals.service import payload_hash
from app.modules.investigation.providers import InvestigationProvider, expected_task_finding
from app.modules.investigation.resolution import (
    MAX_RESOLUTION_ATTEMPTS,
    ResolutionDraft,
    final_resolution,
    review_attempt,
    write_attempt,
)
from app.modules.investigation.resolution_schemas import CriticOutcome
from app.modules.investigation.routing import validate_plan
from app.modules.investigation.schemas import (
    EvidenceLink,
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
    if len(merged) > 65:
        raise ValueError("Too many investigation findings")
    return dict(sorted(merged.items()))


class InvestigationState(TypedDict):
    run_id: UUID
    snapshot: InvoiceSnapshot
    findings: Annotated[dict[str, Finding], merge_findings]
    report: InvestigationReport
    plan: InvestigationPlan
    tool_results: dict[str, ToolResult]
    resolution_attempt: int
    resolution_draft: ResolutionDraft | None
    critic_outcome: CriticOutcome


def build_graph(provider: InvestigationProvider, *, checkpointer=None):
    def capture(state: InvestigationState):
        # Frozen Pydantic contracts are the runtime boundary; TypedDict alone is not validation.
        snapshot = InvoiceSnapshot.model_validate(state["snapshot"])
        return {"snapshot": snapshot}

    def supervise(state: InvestigationState):
        if not hasattr(provider, "plan"):
            raise ValueError("Investigation provider must supply a plan")
        plan = validate_plan(state["snapshot"], provider.plan(state["snapshot"]))
        # Execute each allowlisted tool once before fan-out. Workers share no mutable
        # cache or SQLAlchemy Session; immutable ToolResults are safe to read concurrently.
        snapshot = state["snapshot"]
        box = ReadOnlyTools(snapshot)
        names = sorted({name for task in plan.tasks for name in task.tools})
        if len(names) > 12:
            raise ValueError("Investigation tool budget exceeded")
        cache = {
            name: box.call(
                ToolRequest(
                    name=name,
                    invoice_id=snapshot.invoice_id,
                    supplier_key=snapshot.lookup.supplier_key if snapshot.lookup else "",
                )
            )
            for name in names
        }
        return {"plan": plan, "tool_results": cache, "resolution_attempt": 0}

    def worker(role):
        def execute(state: InvestigationState):
            s = state["snapshot"]
            cache = state["tool_results"]
            findings = {}
            for task in state["plan"].tasks:
                if task.role != role:
                    continue
                evidence = tuple(cache[name] for name in task.tools)
                finding = Finding.model_validate(provider.investigate(s, task, evidence))
                if finding != expected_task_finding(s, task, evidence):
                    raise ValueError("Unsupported investigation output")
                findings[task.task_id] = finding
            return {"findings": findings}

        return execute

    def verified_findings(state):
        snapshot = state["snapshot"]
        # The minimal provider has one allowlisted output per blocker. Unknown citations,
        # altered numeric claims, omissions and unsupported actions never reach storage.
        expected = {
            task.task_id: expected_task_finding(
                snapshot, task, tuple(state["tool_results"][name] for name in task.tools)
            )
            for task in state["plan"].tasks
        }
        if state["findings"] != expected:
            raise ValueError("Unsupported investigation output")
        return tuple(state["findings"].values())

    def write_resolution(state):
        findings = verified_findings(state)
        attempt = state["resolution_attempt"] + 1
        if attempt > MAX_RESOLUTION_ATTEMPTS:
            raise ValueError("Resolution attempt budget exceeded")
        candidate = write_attempt(
            provider, state["snapshot"], findings, attempt, state.get("critic_outcome")
        )
        # Checkpoints retain only valid bounded contracts; malformed provider payloads
        # are neither persisted nor logged, but the critic still records rejection.
        try:
            candidate = ResolutionDraft.model_validate(candidate)
        except (ValueError, TypeError):
            candidate = None
        return {"resolution_attempt": attempt, "resolution_draft": candidate}

    def critic(state):
        result = review_attempt(
            provider, state["snapshot"], verified_findings(state), state["resolution_draft"]
        )
        return {"critic_outcome": result}

    def next_resolution(state):
        if (
            state["critic_outcome"].accepted
            or state["resolution_attempt"] >= MAX_RESOLUTION_ATTEMPTS
        ):
            return "advisory_report"
        return "resolution_writer"

    def report(state: InvestigationState):
        snapshot = state["snapshot"]
        findings = verified_findings(state)
        draft, review = final_resolution(
            snapshot,
            findings,
            state["resolution_draft"],
            state["critic_outcome"],
            state["resolution_attempt"],
        )
        result = InvestigationReport(
            summary=draft.summary,
            findings=draft.findings,
            proposed_action=draft.proposed_action,
            missing_evidence=draft.missing_evidence,
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
            resolution=review,
            citations=snapshot.retrieval.hits if snapshot.retrieval else (),
            evidence_links=tuple(
                EvidenceLink(citation_id=c.citation_id, href=c.href)
                for c in (snapshot.retrieval.hits if snapshot.retrieval else ())
            ),
        )
        return {"report": result}

    return (
        StateGraph(InvestigationState)
        .add_node("capture_snapshot", capture)
        .add_node("supervisor", supervise)
        .add_node("financial", worker("financial"))
        .add_node("supplier", worker("supplier"))
        .add_node("documents", worker("documents"))
        .add_node("resolution_writer", write_resolution)
        .add_node("resolution_critic", critic)
        .add_node("advisory_report", report)
        .add_edge(START, "capture_snapshot")
        .add_edge("capture_snapshot", "supervisor")
        .add_edge("supervisor", "financial")
        .add_edge("supervisor", "supplier")
        .add_edge("supervisor", "documents")
        # All three nodes run, even when a role has no work. This explicit AND join
        # cannot publish an incomplete report or deadlock on an unselected branch.
        .add_edge(["financial", "supplier", "documents"], "resolution_writer")
        .add_edge("resolution_writer", "resolution_critic")
        .add_conditional_edges("resolution_critic", next_resolution)
        .add_edge("advisory_report", END)
        .compile(checkpointer=checkpointer)
    )
