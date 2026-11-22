"""Evidence-root compatibility without relaxing identity, value or currency checks."""

import json
import uuid

import pytest

from app.modules.investigation.live_graph import build_live_graph
from app.modules.investigation.live_policy import (
    _pointer,
    available_paths,
    normalize_references,
    reference_feedback,
    validate_live_draft,
)
from app.modules.investigation.schemas import ToolRequest
from app.modules.investigation.tools import ReadOnlyTools
from tests.test_investigation import snapshot
from tests.test_investigation_gemini import draft, evidence
from tests.test_investigation_live import FakeGemini


def changed(path, **extra):
    original = draft()
    finding = original.findings[0]
    assertion = finding.assertions[0].model_copy(update={"field_path": path, **extra})
    return original.model_copy(
        update={
            "findings": (finding.model_copy(update={"assertions": (assertion,)}),),
        }
    )


@pytest.mark.parametrize(
    "path,count",
    [
        ("/rules/0/expected_amount", 0),
        ("/data/rules/0/expected_amount", 1),
        ("/data/nonexistent", 0),
        ("/data/rules/4/expected_amount", 0),
    ],
)
def test_only_unambiguous_existing_prefix_target_is_normalized(path, count):
    original = changed(path)
    normalized, actual_count = normalize_references(original, evidence())
    assert actual_count == count
    assertion = normalized.findings[0].assertions[0]
    assert assertion.value == original.findings[0].assertions[0].value
    assert assertion.currency == "USD" and assertion.evidence_id == "rules"
    codes = validate_live_draft(snapshot(), normalized, evidence())
    assert ("ASSERTION_PATH_INVALID" not in codes) == (count == 1 or path.startswith("/rules/"))


def test_prefix_never_bypasses_exact_values_currency_or_unknown_backend_id():
    for changes, expected in [
        ({"value": "2300"}, "ASSERTION_VALUE_MISMATCH"),
        ({"currency": "EUR"}, "ASSERTION_CURRENCY_MISMATCH"),
        ({"evidence_id": "invented"}, "ASSERTION_REFERENCE_MISSING"),
    ]:
        normalized, _ = normalize_references(
            changed("/data/rules/0/expected_amount", **changes), evidence()
        )
        assert expected in validate_live_draft(snapshot(), normalized, evidence())


def test_ambiguous_prefix_does_not_guess_between_two_resolving_paths():
    first, second = evidence()
    data = {**first.data, "data": {"rules": [{"expected_amount": "999.0000"}]}}
    delivered = (first.model_copy(update={"data": data}), second)
    normalized, count = normalize_references(changed("/data/rules/0/expected_amount"), delivered)
    assert count == 0
    assert normalized.findings[0].assertions[0].field_path.startswith("/data/")
    assert "ASSERTION_VALUE_MISMATCH" in validate_live_draft(snapshot(), normalized, delivered)


@pytest.mark.parametrize(
    "path,expected",
    [
        ("/a~1b/~0key/0", "exact"),
        ("/list/0", None),
        ("/list/1", False),
    ],
)
def test_rfc_pointer_escapes_and_canonical_array_indexes(path, expected):
    data = {"a/b": {"~key": ["exact"]}, "list": [None, False]}
    actual = _pointer(data, path)
    assert type(actual) is type(expected) and actual == expected
    assert "/a~1b/~0key/0" in available_paths(data)


@pytest.mark.parametrize("path", ["/list/01", "/list/-1", "/list/2", "/list/-", "/a~2b", "list/0"])
def test_invalid_escapes_indexes_and_nonexistent_fields_stay_invalid(path):
    with pytest.raises((KeyError, IndexError, ValueError)):
        _pointer({"list": ["value"], "a~2b": "not-a-valid-escape"}, path)


def test_targeted_feedback_has_rejected_reference_reason_and_valid_leaf_paths():
    feedback = reference_feedback(changed("/missing"), evidence())
    assert feedback[0]["evidence_id"] == "rules"
    assert feedback[0]["rejected_path"] == "/missing"
    assert feedback[0]["reason"] == "ASSERTION_PATH_INVALID"
    assert "/rules/0/expected_amount" in feedback[0]["valid_available_paths"]
    assert "2300.0000" not in json.dumps(feedback)


def test_empty_collections_are_not_advertised_as_valid_scalar_assertions():
    assert available_paths({"sources": [], "empty": {}, "truncated": False}) == ["/truncated"]


def test_absence_evidence_and_missing_assertion_feedback_are_claim_relevant():
    from app.modules.investigation.schemas import LookupSnapshot

    captured = snapshot().model_copy(
        update={
            "lookup": LookupSnapshot(
                supplier_key="synthetic supplier",
                invoice_key="synthetic",
                invoice_total=None,
                policy=None,
            )
        }
    )
    tools = ReadOnlyTools(captured)
    results = tuple(
        tools.call(
            ToolRequest(
                name=name, invoice_id=captured.invoice_id, supplier_key="synthetic supplier"
            )
        )
        for name in ("get_supplier_policy", "get_supporting_documents", "search_evidence")
    )
    assert results[0].data["policy_found"] is False
    assert results[0].data["policy"] is None
    assert all(result.data["has_sources"] is False for result in results[1:])
    original = draft()
    finding = original.findings[0].model_copy(
        update={
            "evidence_ids": (results[1].evidence_id,),
            "assertions": (),
        }
    )
    feedback = reference_feedback(original.model_copy(update={"findings": (finding,)}), results)
    assert feedback[0]["finding_index"] == 0
    assert feedback[0]["reason"] == "SUPPORTED_ASSERTIONS_MISSING"
    assert feedback[0]["relevant_evidence"] == [
        {"evidence_id": results[1].evidence_id, "field_path": "/has_sources", "value": False}
    ]


class OfflineBudget:
    def __init__(self):
        self.calls, self.events = [], []

    def call(self, kind, payload, operation, authorize, estimator=None):
        self.calls.append(kind)
        assert len(self.calls) <= 8
        authorize()
        return operation(30, 2048)

    def tool(self, name):
        pass

    def tool_done(self, *args):
        pass

    def observe(self, kind, **details):
        self.events.append((kind, details))


def execute(provider):
    captured = snapshot()

    class OfflineMCP:
        definitions = [{"name": name} for name in ("get_rule_results", "get_invoice_snapshot")]

        def call(self, name, args):
            assert args == {}
            return ReadOnlyTools(captured).call(
                ToolRequest(
                    name=name,
                    invoice_id=captured.invoice_id,
                    supplier_key="",
                )
            )

    budget = OfflineBudget()
    result = build_live_graph(provider, OfflineMCP(), budget, lambda: None).invoke(
        {"snapshot": captured, "run_id": uuid.uuid4()},
        config={"recursion_limit": 30},
    )
    return result, budget


class RepairProvider(FakeGemini):
    def __init__(self, *, repeat=False, prefix=False):
        super().__init__()
        self.drafts = 0
        self.repeat, self.prefix = repeat, prefix

    def draft(self, history, **kwargs):
        self.drafts += 1
        turn = super().draft(history, **kwargs)
        finding = turn.draft.findings[0]
        assertion = finding.assertions[0]
        if self.prefix or self.repeat or self.drafts == 1:
            path = "/data" + assertion.field_path if self.prefix else "/missing"
            assertion = assertion.model_copy(update={"field_path": path})
        if self.drafts == 2:
            assert "valid_available_paths" in history[-1].parts[0].text
            assert "ASSERTION_PATH_INVALID" in history[-1].parts[0].text
        return turn.model_copy(
            update={
                "draft": turn.draft.model_copy(
                    update={
                        "findings": (finding.model_copy(update={"assertions": (assertion,)}),),
                    }
                )
            }
        )


def test_normalization_is_validated_before_critic_and_published_canonically():
    result, budget = execute(RepairProvider(prefix=True))
    assert result["report"].resolution.accepted
    assert not result["report"].assertions[0]["field_path"].startswith("/data/")
    assert any(kind == "REFERENCES_NORMALIZED" for kind, _ in budget.events)


def test_critic_repair_receives_reasons_without_repeating_tool_selection():
    from app.modules.investigation.live_schemas import LiveCritic

    class CriticRepair(FakeGemini):
        reviews = 0
        drafts = 0

        def draft(self, history, **kwargs):
            self.drafts += 1
            if self.drafts == 2:
                assert "Make uncertainty explicit" in history[-1].parts[0].text
            return super().draft(history, **kwargs)

        def critic(self, *args, **kwargs):
            self.reviews += 1
            return self._turn(
                verdict=LiveCritic(
                    accepted=self.reviews == 2,
                    reasons=("Make uncertainty explicit",) if self.reviews == 1 else (),
                )
            )

    provider = CriticRepair()
    result, budget = execute(provider)
    assert result["report"].resolution.accepted
    assert provider.turn == 2 and provider.drafts == 2
    assert budget.calls == ["investigate"] * 2 + ["draft", "critic", "draft", "critic"]


def test_reference_repair_calls_writer_directly_without_another_investigation_turn():
    provider = RepairProvider()
    result, budget = execute(provider)
    assert result["report"].resolution.accepted
    assert provider.turn == 2 and provider.drafts == 2
    assert budget.calls == ["investigate"] * 2 + ["draft", "draft", "critic"]


def test_identical_reference_failure_stops_early_with_specific_safe_abstention():
    provider = RepairProvider(repeat=True)
    result, budget = execute(provider)
    report = result["report"]
    assert not report.resolution.accepted and not report.assertions
    assert report.termination_code == "INVESTIGATION_INVALID_EVIDENCE_REFERENCES"
    assert provider.turn == 2 and provider.drafts == 2
    assert len(budget.calls) == 4
    assert budget.events[-1][0] == "REPAIR_STOPPED"
    assert "/missing" not in json.dumps(budget.events)


def test_distinct_failed_repairs_exhaust_repair_allowance_not_model_budget():
    class DifferentFailures(RepairProvider):
        def draft(self, history, **kwargs):
            turn = super().draft(history, **kwargs)
            finding = turn.draft.findings[0]
            assertion = finding.assertions[0].model_copy(
                update={
                    "field_path": f"/nonexistent_{self.drafts}",
                }
            )
            return turn.model_copy(
                update={
                    "draft": turn.draft.model_copy(
                        update={
                            "findings": (finding.model_copy(update={"assertions": (assertion,)}),),
                        }
                    )
                }
            )

    provider = DifferentFailures(repeat=True)
    result, budget = execute(provider)
    assert result["report"].termination_code == "INVESTIGATION_REPAIR_EXHAUSTED"
    assert not result["report"].resolution.accepted
    assert provider.drafts == 3 and provider.turn == 2
    assert len(budget.calls) == 5
