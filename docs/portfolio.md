# Portfolio draft

**AI Invoice Exception & Approval Automation | n8n + FastAPI**

An independent demonstration using synthetic supplier invoices. I built a workflow
that ingests invoice PDFs, extracts structured fields through a mock or optional
Gemini adapter, checks deterministic arithmetic and supplier rules, detects exact
and changed-byte duplicates, and holds unsafe invoices for a human decision.

The central feature is safe exception handling: a wrong total cannot be posted
until an authenticated operator corrects it, revalidates it, and approves the
current revision. Posting rechecks rules inside a PostgreSQL transaction; unique
keys and locks prevent duplicate ledger entries. Corrections and decisions retain
an auditable history. The dashboard previews sources and exports posted records
as spreadsheet-safe CSV.

The system includes a Next.js/TypeScript/Tailwind dashboard, modular FastAPI backend,
PostgreSQL migrations, a separately authenticated n8n intake workflow, and a public
read-only synthetic snapshot. The original 16-fixture mock benchmark and automated
tests are reproducible. Mock fixture performance is not evidence of live AI accuracy.

**Verified locally:** authenticated review/posting flow, real PostgreSQL concurrency
and rollback tests, browser workflows, public write denial, and n8n internal intake
nodes/replay with a synthetic PDF. The Gemini SDK wire/error contract is tested
offline. **Not verified live:** Gemini model accuracy, Gmail OAuth, Telegram delivery,
Render/Neon hosting or VM TLS. No public deployment has been performed.

I used coding assistance during implementation. The accompanying learning notes
explain the code paths, financial invariants, evaluation limits and deployment
tradeoffs. This is not certified bookkeeping software and does not make payments,
write to an ERP, certify authenticity or claim client savings.

Phase 2 agentic investigation is planned separately. Do not add LangGraph,
multi-agent claims, retrieval scores or checkpoint recovery to the portfolio
description until those milestones are implemented and measured.

Supporting material: [demo script/video](demo-script.md), [benchmark](benchmark.md),
[architecture](architecture.md), [deployment limits](deployment.md),
[Day 5 report](day-5-progress.md).
