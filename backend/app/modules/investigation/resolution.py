"""Scripted writer plus deterministic critic. Evidence text never becomes instructions."""

from typing import Annotated

from pydantic import Field, ValidationError

from app.modules.investigation.resolution_schemas import CriticOutcome, ResolutionReview
from app.modules.investigation.schemas import (
    Action,
    Contract,
    Digest,
    Finding,
    InvoiceSnapshot,
    Text,
)

MAX_RESOLUTION_ATTEMPTS = 3  # Initial draft and at most two replans.


class ResolutionDraft(Contract):
    summary: Text
    findings: Annotated[tuple[Finding, ...], Field(min_length=1, max_length=65)]
    proposed_action: Action
    missing_evidence: Annotated[tuple[Text, ...], Field(max_length=64)]
    source_revision: Annotated[int, Field(ge=1)]
    source_payload_hash: Digest
    source_validation_batch: Annotated[
        str,
        Field(pattern=r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$"),
    ]


def document_gaps(snapshot):
    if snapshot.documents is None:
        return ()
    kinds = {d.kind for d in snapshot.documents.items}
    gaps = tuple(
        f"No {kind} in bounded supporting evidence capture."
        for kind in sorted({"PO", "RECEIPT", "EMAIL"} - kinds)
    )
    return gaps + (
        ("Supporting evidence capture is truncated; more sources may exist.",)
        if snapshot.documents.truncated
        else ()
    )


def canonical_draft(snapshot: InvoiceSnapshot, findings: tuple[Finding, ...]) -> ResolutionDraft:
    """Finite reviewed mock vocabulary: no free text, arithmetic or implied authorization."""
    # The offline investigators inventory records; none authenticates/reconciles the
    # original document. Even an arithmetic finding alone cannot establish its cause.
    action = "REQUEST_EVIDENCE"
    return ResolutionDraft(
        summary=(
            "Scripted advisory resolution based on verified investigation findings; "
            "human review required."
        ),
        findings=findings,
        proposed_action=action,
        missing_evidence=(
            "Human verification of the original document; supporting texts are not reconciled.",
            *document_gaps(snapshot),
        ),
        source_revision=snapshot.revision,
        source_payload_hash=snapshot.payload_sha256,
        source_validation_batch=str(snapshot.validation_batch_id),
    )


def critique(snapshot, findings, candidate) -> CriticOutcome:
    """Reject malformed output, changed numbers, invented evidence and stale binding in code."""
    try:
        draft = ResolutionDraft.model_validate(candidate)
    except (ValueError, TypeError, ValidationError):
        return CriticOutcome(accepted=False, codes=("INVALID_OUTPUT",))
    expected = canonical_draft(snapshot, findings)
    codes = []
    if (draft.source_revision, draft.source_payload_hash, draft.source_validation_batch) != (
        expected.source_revision,
        expected.source_payload_hash,
        expected.source_validation_batch,
    ):
        codes.append("SOURCE_BINDING")
    expected_ids = {f.task_id: f.evidence_ids for f in findings}
    if any(expected_ids.get(f.task_id) != f.evidence_ids for f in draft.findings):
        codes.append("INVALID_CITATION")
    if draft.findings != expected.findings or draft.summary != expected.summary:
        codes.append("UNSUPPORTED_CLAIM")
    if draft.proposed_action != expected.proposed_action:
        codes.append("UNSAFE_ACTION")
    if draft.missing_evidence != expected.missing_evidence:
        codes.append("MISSING_EVIDENCE")
    return CriticOutcome(accepted=not codes, codes=tuple(codes))


def write_attempt(provider, snapshot, findings, attempt, feedback):
    writer = getattr(provider, "write_resolution", None)
    if writer is None:
        return canonical_draft(snapshot, findings)
    return writer(snapshot, findings, attempt, feedback)


def review_attempt(provider, snapshot, findings, candidate):
    outcome = critique(snapshot, findings, candidate)
    critic = getattr(provider, "critique_resolution", None)
    if outcome.accepted and critic is not None:
        try:
            proposed = CriticOutcome.model_validate(critic(snapshot, findings, candidate))
        except (ValueError, TypeError, ValidationError):
            return CriticOutcome(accepted=False, codes=("INVALID_OUTPUT",))
        if not proposed.accepted or proposed.codes:
            return CriticOutcome(accepted=False, codes=("CRITIC_REJECTED",))
    return outcome


def final_resolution(snapshot, findings, candidate, outcome, attempt):
    if outcome.accepted:
        draft = ResolutionDraft.model_validate(candidate)
        escalated = draft.proposed_action == "REQUEST_EVIDENCE"
    else:
        # Never publish the rejected provider draft, even after the budget is exhausted.
        draft = canonical_draft(snapshot, findings).model_copy(
            update={"proposed_action": "REQUEST_EVIDENCE"}
        )
        escalated = True
    return draft, ResolutionReview(
        accepted=outcome.accepted, escalated=escalated, attempts=attempt, codes=outcome.codes
    )
