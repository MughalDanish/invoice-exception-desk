"""Offline provider boundary, deliberately independent of the extraction adapter."""

from typing import Protocol

from app.modules.investigation.routing import mandatory_plan
from app.modules.investigation.schemas import (
    Finding,
    Findings,
    InvestigationPlan,
    InvoiceSnapshot,
    PlanTask,
    RuleEvidence,
    ToolRequest,
    ToolResult,
)
from app.modules.investigation.tools import ReadOnlyTools


class InvestigationProvider(Protocol):
    def plan(self, snapshot: InvoiceSnapshot) -> InvestigationPlan: ...

    def investigate(
        self, snapshot: InvoiceSnapshot, task: PlanTask, evidence: tuple[ToolResult, ...]
    ) -> Finding: ...


def expected_finding(
    snapshot: InvoiceSnapshot, rule: RuleEvidence, evidence: tuple[ToolResult, ...] | None = None
) -> Finding:
    """Deterministic grounded mock template, not a claim of live agent reasoning."""
    task = next(t for t in mandatory_plan(snapshot).tasks if t.task_id == str(rule.id))
    if evidence is None:
        box = ReadOnlyTools(snapshot)
        evidence = tuple(
            box.call(
                ToolRequest(
                    name=name,
                    invoice_id=snapshot.invoice_id,
                    supplier_key=snapshot.lookup.supplier_key if snapshot.lookup else "",
                )
            )
            for name in task.tools
        )
    if tuple(r.name for r in evidence) != task.tools:
        raise ValueError("Required tool evidence missing")
    supported = (
        rule.code == "TOTAL_MISMATCH"
        and rule.expected_amount is not None
        and rule.observed_amount is not None
        and snapshot.currency is not None
    )
    claim = (
        f"Recorded TOTAL_MISMATCH validation: expected {rule.expected_amount} "
        f"{snapshot.currency}; observed {rule.observed_amount} {snapshot.currency}. "
        "The original document must be checked to distinguish extraction error "
        "from a discrepancy in the document."
        if supported
        else f"Blocker {rule.code} is recorded. This mock milestone cannot investigate its cause."
    )
    lookup = snapshot.lookup
    if lookup is not None and rule.code == "UNAPPROVED_VENDOR":
        supported = bool(lookup.supplier_key)
        claim = (
            evidence[1].facts[0]
            + " Current validation still requires supplier review and revalidation."
        )
    elif lookup is not None and rule.code == "DUPLICATE_INVOICE":
        supported = bool(lookup.supplier_key and lookup.invoice_key)
        claim = " ".join(evidence[1].facts)
        if lookup.duplicates_truncated or lookup.ledger_matches_truncated:
            claim += " Candidate results are truncated."
    elif lookup is not None and rule.code == "AMOUNT_OUTLIER":
        policy = lookup.policy
        supported = bool(
            policy
            and policy.amount_limit is not None
            and snapshot.currency
            and policy.currency == snapshot.currency
            and lookup.invoice_total is not None
        )
        if supported:
            claim = (
                f"Recorded AMOUNT_OUTLIER; captured invoice total {lookup.invoice_total} "
                f"{snapshot.currency}; supplier threshold {policy.amount_limit} {policy.currency}. "
                + " ".join(evidence[2].facts)
                + " Revalidate before any financial action."
            )
        else:
            claim = (
                "Supplier threshold or comparable currency evidence is unavailable; "
                "request evidence."
            )
    return Finding(
        task_id=str(rule.id),
        claim=claim,
        evidence_ids=(f"validation:{rule.id}",) + tuple(r.evidence_id for r in evidence),
        status="SUPPORTED" if supported else "INSUFFICIENT",
    )


class MockInvestigationProvider:
    """Scripted findings exercise the real graph, not live model reasoning."""

    def plan(self, snapshot: InvoiceSnapshot) -> InvestigationPlan:
        return mandatory_plan(snapshot)

    def investigate(
        self,
        snapshot: InvoiceSnapshot,
        task: PlanTask | None = None,
        evidence: tuple[ToolResult, ...] | None = None,
    ) -> Finding | Findings:
        # Optional task retains the Day 6 offline helper; graph execution always supplies it.
        if task is None:
            return Findings(items=tuple(expected_finding(snapshot, r) for r in snapshot.blockers))
        return expected_task_finding(snapshot, task, evidence)


def expected_task_finding(snapshot, task, evidence=None) -> Finding:
    if task.kind != "documents":
        rule = next(r for r in snapshot.blockers if r.id == task.rule_id)
        return expected_finding(snapshot, rule, evidence)
    if evidence is None:
        evidence = (
            ReadOnlyTools(snapshot).call(
                ToolRequest(
                    name="get_supporting_documents",
                    invoice_id=snapshot.invoice_id,
                    supplier_key=snapshot.lookup.supplier_key if snapshot.lookup else "",
                )
            ),
        )
    if tuple(r.name for r in evidence) != task.tools:
        raise ValueError("Required document evidence missing")
    # Inventory only: presence does not substantiate amounts or prove authenticity.
    return Finding(
        task_id=task.task_id,
        claim=" ".join(evidence[0].facts)
        + " Contents have not been reconciled; human review required.",
        evidence_ids=(evidence[0].evidence_id,),
        status="INSUFFICIENT",
    )
