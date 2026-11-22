"""Day 10 deterministic critic, bounded repairs and safe abstention (no model calls)."""

import uuid

import pytest

from app.modules.investigation.graph import build_graph
from app.modules.investigation.providers import MockInvestigationProvider, expected_finding
from app.modules.investigation.resolution import canonical_draft, critique
from app.modules.investigation.resolution_schemas import CriticOutcome
from tests.test_investigation import snapshot


def execute(provider=None):
    return build_graph(provider or MockInvestigationProvider()).invoke(
        {"run_id": uuid.uuid4(), "snapshot": snapshot(), "findings": {}},
        config={"recursion_limit": 12, "max_concurrency": 3, "callbacks": []},
    )


def test_default_writer_is_grounded_and_explicitly_escalates_missing_original():
    report = execute()["report"]
    assert report.resolution.accepted and report.resolution.escalated
    assert report.resolution.attempts == 1
    assert report.proposed_action == "REQUEST_EVIDENCE"
    assert "2300.0000" in report.findings[0].claim
    assert "2500.0000" in report.findings[0].claim
    assert report.advisory_only


@pytest.mark.parametrize(
    "attack,code",
    [
        ("amount", "UNSUPPORTED_CLAIM"),
        ("claim", "UNSUPPORTED_CLAIM"),
        ("citation", "INVALID_CITATION"),
        ("revision", "SOURCE_BINDING"),
        ("hash", "SOURCE_BINDING"),
        ("batch", "SOURCE_BINDING"),
        ("action", "UNSAFE_ACTION"),
        ("missing", "MISSING_EVIDENCE"),
        ("omitted", "INVALID_OUTPUT"),
    ],
)
def test_critic_rejects_unsupported_or_stale_drafts(attack, code):
    s = snapshot()
    findings = (expected_finding(s, s.blockers[0]),)
    draft = canonical_draft(s, findings)
    if attack in {"amount", "claim", "citation"}:
        finding = findings[0]
        updates = {
            "amount": {"claim": finding.claim.replace("2300.0000", "9999.0000")},
            "claim": {"claim": "Supplier approved this invoice; payment is authorized."},
            "citation": {"evidence_ids": ("source:invented:v9",)},
        }
        draft = draft.model_copy(update={"findings": (finding.model_copy(update=updates[attack]),)})
    else:
        updates = {
            "revision": {"source_revision": 2},
            "hash": {"source_payload_hash": "c" * 64},
            "batch": {"source_validation_batch": str(uuid.uuid4())},
            "action": {"proposed_action": "REQUEST_CORRECTED_INVOICE"},
            "missing": {"missing_evidence": ()},
            "omitted": {"findings": ()},
        }
        draft = draft.model_copy(update=updates[attack])
    result = critique(s, findings, draft)
    assert not result.accepted and code in result.codes


def test_two_repairs_maximum_and_rejected_text_never_published():
    class Untrusted(MockInvestigationProvider):
        attempts = []

        def write_resolution(self, snapshot, findings, attempt, feedback):
            self.attempts.append((attempt, feedback))
            return canonical_draft(snapshot, findings).model_copy(
                update={"summary": "PRIVATE MALICIOUS UNSUPPORTED CLAIM"}
            )

    provider = Untrusted()
    result = execute(provider)
    report = result["report"]
    assert [a for a, _ in provider.attempts] == [1, 2, 3]
    assert provider.attempts[1][1].codes == ("UNSUPPORTED_CLAIM",)
    assert report.resolution.attempts == 3
    assert not report.resolution.accepted and report.resolution.escalated
    assert "PRIVATE MALICIOUS" not in report.model_dump_json()
    assert report.proposed_action == "REQUEST_EVIDENCE"


def test_writer_can_repair_using_sanitized_feedback_without_repeating_tools():
    class Repair(MockInvestigationProvider):
        count = 0

        def investigate(self, *args):
            self.count += 1
            return super().investigate(*args)

        def write_resolution(self, snapshot, findings, attempt, feedback):
            draft = canonical_draft(snapshot, findings)
            if attempt == 1:
                assert feedback is None
                return draft.model_copy(update={"source_revision": 999})
            assert feedback.codes == ("SOURCE_BINDING",)
            return draft

    provider = Repair()
    report = execute(provider)["report"]
    assert report.resolution.accepted and report.resolution.attempts == 2
    assert provider.count == 1


def test_probabilistic_critic_cannot_overrule_deterministic_gate():
    class FalseApproval(MockInvestigationProvider):
        def write_resolution(self, snapshot, findings, attempt, feedback):
            return canonical_draft(snapshot, findings).model_copy(update={"summary": "Invented"})

        def critique_resolution(self, *args):
            pytest.fail("Unsupported draft must fail before model critic")

    report = execute(FalseApproval())["report"]
    assert not report.resolution.accepted and report.resolution.attempts == 3


def test_scripted_critic_can_reject_valid_output_but_not_bypass_budget():
    class Skeptical(MockInvestigationProvider):
        def critique_resolution(self, *args):
            return CriticOutcome(accepted=False, codes=("CRITIC_REJECTED",))

    report = execute(Skeptical())["report"]
    assert report.resolution.codes == ("CRITIC_REJECTED",)
    assert report.resolution.attempts == 3 and report.resolution.escalated


def test_malformed_and_forbidden_action_output_is_not_checkpointed_raw():
    class Malformed(MockInvestigationProvider):
        def write_resolution(self, *args):
            return {"proposed_action": "POST", "secret": "Do not persist"}

    result = execute(Malformed())
    assert result["resolution_draft"] is None
    assert result["report"].resolution.codes == ("INVALID_OUTPUT",)
    assert "Do not persist" not in result["report"].model_dump_json()
