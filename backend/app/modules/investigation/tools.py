"""Allowlisted tools over an immutable, server-scoped read projection.

These functions receive no Session, connection, paths, arbitrary SQL or network client.
"""

from app.modules.approvals.service import payload_hash
from app.modules.investigation.schemas import InvoiceSnapshot, ToolRequest, ToolResult


class ReadOnlyTools:
    def __init__(self, snapshot: InvoiceSnapshot):
        self.snapshot = InvoiceSnapshot.model_validate(snapshot)

    def call(self, request: ToolRequest) -> ToolResult:
        request = ToolRequest.model_validate(request)
        s = self.snapshot
        lookup = s.lookup
        if request.invoice_id != s.invoice_id or request.supplier_key != (
            lookup.supplier_key if lookup else ""
        ):
            raise ValueError("Tool scope mismatch")
        name = request.name
        digest = payload_hash(s.model_dump(mode="json"))
        reference = f"lookup:{digest}:{name}"
        if name == "get_invoice_snapshot":
            return ToolResult(
                name=name,
                evidence_id=reference,
                status="NOT_READ",
                facts=(
                    f"Original document SHA-256: {s.document_sha256}; document contents not read.",
                ),
            )
        if name == "get_rule_results":
            return ToolResult(
                name=name,
                evidence_id=reference,
                status="FOUND",
                facts=(
                    f"Current batch {s.validation_batch_id}; "
                    f"{len(s.blockers)} failed blocking rules.",
                ),
            )
        if lookup is None or not lookup.supplier_key:
            return ToolResult(
                name=name,
                evidence_id=reference,
                status="MISSING",
                facts=("Scoped structured lookup evidence is unavailable.",),
            )
        if name == "find_duplicate_candidates":
            return ToolResult(
                name=name,
                evidence_id=reference,
                status="FOUND",
                facts=(
                    f"Scoped active invoice candidates: {len(lookup.duplicates)}; "
                    f"matching ledger entries: {len(lookup.ledger_matches)}.",
                    "Results are a bounded sample, not proof of fraud or authorization to reject.",
                ),
            )
        if name == "get_supplier_policy":
            policy = lookup.policy
            facts = (
                ("No supplier registry record matches the scoped normalized identity.",)
                if policy is None
                else (
                    "Supplier registry approval: "
                    f"{'approved' if policy.approved else 'unapproved'}.",
                    f"Policy currency: {policy.currency or 'not provided'}; "
                    f"amount limit: {policy.amount_limit or 'not provided'}.",
                )
            )
            return ToolResult(name=name, evidence_id=reference, status="FOUND", facts=facts)
        if name == "get_supplier_history":
            return ToolResult(
                name=name,
                evidence_id=reference,
                status="FOUND",
                facts=(
                    f"Recent same-currency ledger sample: {len(lookup.history)} entries; "
                    f"truncated: {lookup.history_truncated}.",
                    "No statistical anomaly or supplier legitimacy is inferred from this sample.",
                ),
            )
        raise ValueError("Tool is not allowlisted")
