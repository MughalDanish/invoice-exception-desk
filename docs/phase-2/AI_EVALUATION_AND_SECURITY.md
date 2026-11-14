# Evaluation, reliability and financial safety

## Non-negotiable invariants
- AI cannot modify invoices, suppliers, policy, approvals or ledger; no mutation tool exists. Operator edits use existing expected revision workflow; fresh deterministic validation and existing approval hash binding remain required.
- Reports are tied to revision, payload hash, validation batch and evidence versions. A stale report cannot represent current facts. Existing unique ledger/business keys and row/advisory locks remain unchanged.
- Treat invoices, emails, retrieved text and model output as untrusted. Never execute instructions in evidence; allowlisted tools with strict schemas and server-derived scope, parameterized SQL, bounded reads, no external browsing, no arbitrary file access. Reject unknown tool/action names and spoofed IDs. Render plain escaped text; no model-generated HTML.
- Do not expose secrets, full prompts, raw model output or real financial documents in logs or external traces. Synthetic data only; live keys in env, explicit opt-in. No real ERP or payment. Existing local Basic auth is not production auth. Public read-only routes must not run models or reveal private files. Keep integration key separate.
- Enforce limits at execution boundary, not in prompt alone. Treat model critic as probabilistic; code validates schemas, evidence existence, numeric facts and action allowlist. Missing evidence is a supported outcome. Human reviews semantic support; no certification claims.

## Dataset and evaluation protocol
Keep original 16 fixtures and hash answer keys intact. New synthetic corpus versioned independently: clean/control, wrong totals, changed-byte duplicates, unapproved vendor, amount outlier, PO amendments, missing goods receipts, contradictory emails, insufficient evidence, stale revisions, adversarial documents. Generate about 100 labeled cases if feasible; record seed, exact counts and provenance. Label expected blocker, mandatory tools, acceptable action set, evidence IDs, forbidden claims. Separate development examples from frozen held-out cases by scenario family where feasible; no answers in model context or retrieval index. Human review a sample of semantic labels. Compare deterministic rules-only baseline, single LLM with tools, and graph approach under equivalent evidence and budgets. Report failures, denominators, model/provider versions, prompts and cost; mock scores measure execution not AI reasoning.

| Metric | Definition | Aspirational target, not result |
|---|---|---|
| Field extraction accuracy | exact normalized correct labeled fields / labeled fields | 98% |
| Exception recall | TP/(TP+FN) on labeled blocked cases | 95% |
| Routing | cases with appropriate task set / labeled cases; also mandatory task recall | 95%; mandatory checks 100% in tests |
| Retrieval recall@5 | relevant labeled evidence retrieved in top 5 / labeled relevant evidence, macro average | 90% |
| Evidence support | supported audited factual claims / audited factual claims | report actual; no unsupported high-risk recommendation accepted in tests |
| Resolution | allowed action set match / labeled cases | report by scenario; compare baseline |
| Recovery | completed safely after injected failure / recovery trials | 100% in defined tests |
| Unauthorized writes | count of writes caused by AI/integration/public access tests | 0 |
| Latency/cost | p50/p95 wall time, calls, input/output tokens and actual provider cost if known | measure; separate mock/live |

Report precision/recall with TP/FP/FN, sample sizes, missing outputs and failure rates; never silently exclude timeouts. If no live API credentials, label all model quality metrics NOT RUN; scripted fixture output is not live accuracy. Cost estimates need dated pricing input and must be marked estimates. Keep reproducible JSON/CSV run outputs and concise benchmark markdown, not private prompts.

## Required adversarial and failure tests
Invalid schema, malicious invoice/email instructions, cross-supplier evidence lookup, invented evidence ID, conflicting citations, unknown action, duplicated task completion, timeout/429/5xx, expired lease and late worker, crash between checkpoint and result commit, concurrent enqueue, cancel during execution, correction while running, changed validation batch, posted/rejected invoice, unknown model usage, budget exhaustion, unauthorized user/integration/public writes. Assert ledger and approval rows unchanged in all investigation tests. Test original 142-test baseline (actual counts may grow), browser workflows and migration compatibility. Use isolated random DB schemas and real PostgreSQL for race tests; never destructive tests against demo data.

## Observability
Emit run/task IDs, timestamps, node status, latency, sanitized error codes, tool names and counts, model identifier, tokens and checkpoint/retry counters. Record concise decision summaries, not hidden reasoning. Optional LangSmith only with redaction and explicit consent. Define retention for synthetic run records (e.g. 30 days configurable); cleanup via explicit maintenance command, never delete existing immutable financial audits. Document backup and reset for demo.
