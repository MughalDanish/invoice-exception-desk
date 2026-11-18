"""Offline provider boundary, deliberately independent of the extraction adapter."""

from typing import Protocol

from app.modules.investigation.schemas import Finding, Findings, InvoiceSnapshot, RuleEvidence


class InvestigationProvider(Protocol):
    def investigate(self, snapshot: InvoiceSnapshot) -> Findings: ...


def expected_finding(snapshot: InvoiceSnapshot, rule: RuleEvidence) -> Finding:
    """Day 6 supports recorded total evidence only; other blockers explicitly abstain."""
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
    return Finding(
        task_id=str(rule.id),
        claim=claim,
        evidence_ids=(f"validation:{rule.id}",),
        status="SUPPORTED" if supported else "INSUFFICIENT",
    )


class MockInvestigationProvider:
    """Scripted findings exercise the real graph, not live model reasoning."""

    def investigate(self, snapshot: InvoiceSnapshot) -> Findings:
        return Findings(items=tuple(expected_finding(snapshot, rule) for rule in snapshot.blockers))
