"""Versioned live graph: every model/tool boundary is independently checkpointed."""

import json
import logging
import time
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.modules.approvals.service import payload_hash
from app.modules.evidence.schemas import Citation
from app.modules.investigation.gemini_provider import (
    function_result_content,
    initial_history,
)
from app.modules.investigation.live_policy import (
    evidence_manifest,
    normalize_references,
    reference_feedback,
    validate_live_draft,
)
from app.modules.investigation.live_schemas import ProtocolContent, ProtocolPart
from app.modules.investigation.resolution_schemas import ResolutionReview
from app.modules.investigation.routing import mandatory_plan
from app.modules.investigation.schemas import (
    EvidenceLink,
    Finding,
    InvestigationReport,
    InvoiceSnapshot,
)


class LiveState(TypedDict):
    snapshot: InvoiceSnapshot
    run_id: object
    history: tuple
    pending_calls: tuple
    tool_results: dict
    draft: object
    repairs: int
    decision: str
    report: InvestigationReport
    rejected_signatures: tuple
    repair_target: str
    termination_code: str | None
    rejection_details: dict


def build_live_graph(provider, mcp, budget, authorize, *, checkpointer=None):
    def observe(kind, **details):
        observer = getattr(budget, "observe", None)
        if observer:
            observer(kind, **details)

    def capture(state):
        snapshot = InvoiceSnapshot.model_validate(state["snapshot"])
        names = sorted({name for t in mandatory_plan(snapshot).tasks for name in t.tools})
        return {
            "history": initial_history([b.code for b in snapshot.blockers], names),
            "tool_results": {},
            "repairs": 0,
            "rejected_signatures": (),
            "termination_code": None,
        }

    def model(state):
        history = state["history"]
        definitions = mcp.definitions
        if len(history) == 1:
            # Rule evidence is the deterministic starting point. Only later
            # turns expose all tools for Gemini's dynamic evidence selection.
            definitions = [d for d in definitions if d["name"] == "get_rule_results"]
        result = budget.call(
            "investigate",
            {"history": [c.model_dump(mode="json") for c in history], "tools": definitions},
            lambda timeout, output: provider.step(
                history, definitions, timeout_seconds=timeout, max_output_tokens=output
            ),
            authorize,
            getattr(provider, "estimate_input_tokens", None),
        )
        if result.content is None:
            raise ValueError("MODEL_CONTENT_MISSING")
        if len(history) >= 32:
            raise ValueError("MODEL_HISTORY_LIMIT")
        return {"history": (*history, result.content), "pending_calls": result.calls}

    def tools(state):
        history = list(state["history"])
        results = dict(state["tool_results"])
        names = {d["name"] for d in mcp.definitions}
        # The model can return parallel requests, but this host deliberately
        # executes serially under one run budget and one authorized MCP session.
        for call in state["pending_calls"]:
            budget.tool(call.name if call.name in names else "UNAPPROVED_TOOL")
            authorize()
            if call.name not in names or call.args != {}:
                logging.getLogger(__name__).warning(
                    "Investigation tool denied tool=%s nonempty_arguments=%s",
                    call.name if call.name in names else "UNAPPROVED_TOOL",
                    bool(call.args),
                )
                raise ValueError("MODEL_TOOL_NOT_ALLOWED")
            started = time.monotonic()
            if hasattr(mcp, "timeout"):
                mcp.timeout = min(mcp.timeout, budget.remaining())
            result = mcp.call(call.name, call.args)
            if call.name in results and results[call.name] != result:
                raise ValueError("CONFLICTING_TOOL_EVIDENCE")
            budget.tool_done(
                call.name, result, int((time.monotonic() - started) * 1000), call.name in results
            )
            results[call.name] = result
            history.append(function_result_content(call, result))
        if len(history) > 48:
            raise ValueError("MODEL_HISTORY_LIMIT")
        return {"history": tuple(history), "tool_results": results, "pending_calls": ()}

    def draft(state):
        result = budget.call(
            "draft",
            [c.model_dump(mode="json") for c in state["history"]],
            lambda timeout, output: provider.draft(
                state["history"], timeout_seconds=timeout, max_output_tokens=output
            ),
            authorize,
            getattr(provider, "estimate_input_tokens", None),
        )
        if result.draft is None:
            raise ValueError("MODEL_DRAFT_MISSING")
        return {"draft": result.draft}

    def review(state):
        delivered = tuple(state["tool_results"].values())
        candidate, normalized = normalize_references(state["draft"], delivered)
        if normalized:
            observe("REFERENCES_NORMALIZED", count=normalized)
        codes = validate_live_draft(state["snapshot"], candidate, delivered)
        critic_reasons = ()
        if not codes:
            result = budget.call(
                "critic",
                {
                    "draft": candidate.model_dump(mode="json"),
                    "delivered": [r.model_dump(mode="json") for r in delivered],
                },
                lambda timeout, output: provider.critic(
                    candidate, delivered, timeout_seconds=timeout, max_output_tokens=output
                ),
                authorize,
                getattr(provider, "estimate_input_tokens", None),
            )
            if result.verdict is None or not result.verdict.accepted:
                codes = ("SEMANTIC_CRITIC_REJECTED",)
                critic_reasons = result.verdict.reasons[:3] if result.verdict else ()
        if not codes:
            return {"decision": "accepted", "draft": candidate, "termination_code": None}
        repairs = state["repairs"]
        reference_codes = {
            "ASSERTION_PATH_INVALID",
            "EVIDENCE_NOT_DELIVERED",
            "ASSERTION_REFERENCE_MISSING",
            "ASSERTION_VALUE_MISMATCH",
            "ASSERTION_CURRENCY_MISSING",
            "ASSERTION_CURRENCY_MISMATCH",
            "ASSERTION_DECIMAL_INVALID",
        }
        references_only = set(codes) <= reference_codes
        signature = payload_hash(
            {
                "codes": codes,
                "references": [
                    {
                        "ids": f.evidence_ids,
                        "assertions": [a.model_dump(mode="json") for a in f.assertions],
                    }
                    for f in candidate.findings
                ]
                if references_only
                else candidate.model_dump(mode="json"),
            }
        )
        signatures = state.get("rejected_signatures", ())
        repeated = signature in signatures
        observe("REPORT_REJECTED", codes=list(codes), repair=repairs, repeated=repeated)
        issues = reference_feedback(candidate, delivered)
        rejection_details = {
            "codes": list(codes),
            "findings": issues,
            "critic_reasons": critic_reasons,
            "repair": repairs,
        }
        if repeated or repairs >= 2:
            termination = (
                "INVESTIGATION_INVALID_EVIDENCE_REFERENCES"
                if repeated and references_only
                else "INVESTIGATION_REPEATED_REPAIR"
                if repeated
                else "INVESTIGATION_REPAIR_EXHAUSTED"
            )
            observe("REPAIR_STOPPED", code=termination, repair=repairs)
            return {
                "decision": "insufficient",
                "draft": candidate,
                "termination_code": termination,
                "rejection_details": rejection_details,
            }
        feedback = ProtocolContent(
            role="user",
            parts=(
                ProtocolPart(
                    text="Draft rejected by policy/critic: "
                    + ", ".join(codes)
                    + ". Reference root is the cited data object itself. Do not prepend /data. "
                    + "Use scalar leaf paths and exact delivered values. "
                    + "Targeted reference feedback: "
                    + json.dumps(issues)[:8000]
                    + ". Critic feedback: "
                    + json.dumps(critic_reasons)[:2000]
                    + ". Rejected structured draft: "
                    + json.dumps(candidate.model_dump(mode="json"))[:12000]
                    + ". Revisit evidence as needed; do not invent missing facts."
                ),
            ),
        )
        return {
            "decision": "repair",
            "rejection_details": rejection_details,
            "repairs": repairs + 1,
            "rejected_signatures": (*signatures, signature),
            "repair_target": "model" if "MANDATORY_TOOLS_MISSING" in codes else "draft",
            "draft": candidate,
            "history": (*state["history"], feedback),
        }

    def publish(state):
        authorize()
        snapshot = state["snapshot"]
        accepted = state["decision"] == "accepted"
        draft = state["draft"]
        if accepted and validate_live_draft(snapshot, draft, tuple(state["tool_results"].values())):
            raise ValueError("FINAL_REPORT_POLICY_REJECTED")
        manifest = evidence_manifest(tuple(state["tool_results"].values()))
        # Never publish a rejected model finding, even after repair exhaustion.
        findings = (
            tuple(
                Finding(
                    task_id=f"live:{index}",
                    claim=f.claim,
                    evidence_ids=f.evidence_ids,
                    status="INSUFFICIENT" if f.status == "HYPOTHESIS" else f.status,
                )
                for index, f in enumerate(draft.findings)
            )
            if accepted
            else (
                Finding(
                    task_id="live:insufficient",
                    claim="Investigation could not establish a supported resolution.",
                    evidence_ids=(next(iter(manifest)),)
                    if manifest
                    else (f"validation:{snapshot.blockers[0].id}",),
                    status="INSUFFICIENT",
                ),
            )
        )
        captured = {
            c.citation_id: c for c in (snapshot.retrieval.hits if snapshot.retrieval else ())
        }
        for source in snapshot.documents.items if snapshot.documents else ():
            citation = Citation(
                **source.model_dump(exclude={"text"}), excerpt=source.text, end=len(source.text)
            )
            captured[citation.citation_id] = citation
        citations = tuple(c for key, c in captured.items() if key in manifest)
        return {
            "report": InvestigationReport(
                summary=draft.summary
                if accepted
                else "Live investigation requires further human evidence review.",
                findings=findings,
                proposed_action=draft.proposed_action if accepted else "REQUEST_EVIDENCE",
                missing_evidence=draft.uncertainties
                if accepted
                else ("No supported resolution was accepted within the repair allowance.",),
                limitations=(
                    *(draft.limitations[:6] if accepted else ()),
                    "Live AI advice proves neither authenticity nor financial authorization.",
                    "Human review and fresh deterministic validation remain required.",
                ),
                source_revision=snapshot.revision,
                source_payload_hash=snapshot.payload_sha256,
                source_validation_batch=snapshot.validation_batch_id,
                mode="gemini",
                tools_used=tuple(sorted(state["tool_results"])),
                plan=mandatory_plan(snapshot),
                citations=citations,
                evidence_links=tuple(
                    EvidenceLink(citation_id=c.citation_id, href=c.href) for c in citations
                ),
                resolution=ResolutionReview(
                    accepted=accepted,
                    escalated=not accepted or draft.proposed_action == "REQUEST_EVIDENCE",
                    attempts=state["repairs"] + 1,
                    codes=() if accepted else ("CRITIC_REJECTED",),
                ),
                assertions=tuple(
                    a.model_dump(mode="json") for f in draft.findings for a in f.assertions
                )
                if accepted
                else (),
                uncertainties=draft.uncertainties
                if accepted
                else ("Human investigation required.",),
                resolution_rationale=draft.resolution_rationale
                if accepted
                else "Unsupported model output was withheld.",
                model=provider.model,
                provider_version="gemini-mcp-v1",
                termination_code=state.get("termination_code"),
            )
        }

    return (
        StateGraph(LiveState)
        .add_node("capture", capture)
        .add_node("model", model)
        .add_node("tools", tools)
        .add_node("draft", draft)
        .add_node("review", review)
        .add_node("publish", publish)
        .add_edge(START, "capture")
        .add_edge("capture", "model")
        .add_conditional_edges("model", lambda s: "tools" if s["pending_calls"] else "draft")
        .add_conditional_edges(
            "tools",
            lambda s: (
                "draft"
                if {name for task in mandatory_plan(s["snapshot"]).tasks for name in task.tools}
                <= s["tool_results"].keys()
                else "model"
            ),
        )
        .add_edge("draft", "review")
        .add_conditional_edges(
            "review",
            lambda s: s.get("repair_target", "model") if s["decision"] == "repair" else "publish",
        )
        .add_edge("publish", END)
        .compile(checkpointer=checkpointer)
    )
