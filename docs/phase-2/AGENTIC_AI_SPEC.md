# Phase 2 product and agent specification

## Product objective
Evolve the existing exception queue into an evidence-grounded investigation assistant for small bookkeeping firms, wholesalers and construction companies. It explains why a blocked invoice is questionable, identifies missing evidence and proposes a safe operator action. It does not certify authenticity or authorize payment. Keep the original upload, extract, validate, correct, review and internal ledger workflow.

## Revised Day 13 delivery requirement (authorized)

Implement a genuinely live Gemini investigator, not solely a scripted framework.
Use the existing configured model if verified compatible with function calling.
The host must expose authorized MCP definitions, execute model-selected calls
through an actual stdio MCP client/server connection and return evidence for
subsequent model turns. Keep mocks separately available. Initial prompts must not
contain all evidence; acceptance includes withheld synthetic facts and changed
evidence producing changed conclusions/uncertainties. See the detailed
[Day 13 plan](DAY_13_LIVE_INVESTIGATION_PLAN.md), authorized on 19 November 2026. See milestone reports for actual verification.

The existing role table below describes responsibilities, not a requirement for
one paid model/process per role. Day 13 implements one bounded live investigator
covering mandatory objectives, followed by a writer/critic and deterministic gate.
Actual existing tools are the seven `ToolName` entries; names below such as
`get_purchase_order` are conceptual future capabilities, not implemented tools.
Structured live reports must additionally expose bounded resolution rationale,
typed financial assertions and unresolved uncertainties. Preserve existing fields,
exact money/currency, source binding and advisory actions; support old mock reports.

## Vertical slice and scope
Start with NEEDS_REVIEW invoices that have a current validation batch and usable extracted fields. Include wrong total, duplicate, amount outlier and unknown vendor. Add synthetic purchase order, receipt and email evidence for a price/quantity discrepancy later. PO/receipt matching is new Phase 2 evidence functionality, not an existing feature or an automatic new posting rule. No real mailbox access, supplier contact, bank account modification, payments or ERP integration. Bank-change investigation is an optional synthetic future case, not release scope.

Example: existing invoice B-002 has subtotal 2000, tax 300 and total 2500 USD. An investigation should cite the invoice and deterministic TOTAL_MISMATCH evidence; suggest verifying the original document or obtaining a corrected invoice, not silently substituting 2300. If operator independently corrects fields, existing revalidation and approval are required. A new scenario with PO 5000 and invoice 5500 may cite an amended PO and email, but email alone never authorizes a financial change. Missing receipt or amendment -> request evidence.

## Components and permissions
| Component | Input | Output | Allowed tools |
|---|---|---|---|
| Supervisor | Snapshot, blockers, remaining budget | Typed plan with allowlisted tasks | No direct financial tools |
| Arithmetic/identity investigator | Rule results, invoice snapshot | Findings with exact evidence references | get_rule_results, get_invoice_snapshot, find_duplicate_candidates |
| Supplier/history investigator | Vendor ID, invoice identity | Historical anomalies and gaps | get_supplier_policy, get_supplier_history, get_ledger_matches |
| Document investigator | Invoice/PO IDs, search scope | Relevant source excerpts and gaps | get_purchase_order, get_goods_receipts, search_evidence |
| Resolution writer | Verified findings | Advisory action, claims, missing evidence | No mutations; no new tool access |
| Critic | Recommendation, evidence IDs | Supported/unsupported claims and retry reason | Read cited evidence only |
| Policy gate (code) | Validated result, current revision, budgets | Accept advisory report, stale or escalate | No posting or approval |

Start with supervisor plus two worker roles, then expand only when evaluation demonstrates value. Workers may be tool-using LLM nodes or deterministic functions; do not create agents for arithmetic or DB lookup alone. Mandatory tasks derive from blocker codes in code; model may select additional tasks but cannot skip mandatory checks. Unknown vendor -> supplier registry; duplicate -> exact structured lookup; total mismatch -> arithmetic and original evidence; outlier -> supplier policy/history; PO mismatch -> PO/receipt evidence. Parallelize independent tasks; no agent-to-agent uncontrolled messages.

## Output contract
Report: summary, findings [{claim, evidence_ids, status: SUPPORTED|CONTRADICTED|INSUFFICIENT}], proposed_action enum REQUEST_CORRECTED_INVOICE|REQUEST_EVIDENCE|REVIEW_DUPLICATE|REVIEW_SUPPLIER|REVIEW_POLICY|NO_RECOMMENDATION, missing_evidence[], limitations[], source_revision, source_payload_hash, source_validation_batch. Never output APPROVE or POST as a proposed action. UI shows a read-only advisory report beside existing review controls. Acknowledge report separately from financial approval. If revision changes, discard applicability and label report stale; rerun explicitly.
