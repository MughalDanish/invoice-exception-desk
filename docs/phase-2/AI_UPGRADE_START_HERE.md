# Invoice Exception Desk — Phase 2 execution entry point

## Current checkpoint and next authorization

Days 6–12 are implemented with a scripted investigation provider. Day 13 has been
revised to require **live Gemini investigation through an MCP client**, not only
budget controls or an optional model comparison. Review the findings, security
boundaries, implementation steps and acceptance gates in
[DAY_13_LIVE_INVESTIGATION_PLAN.md](DAY_13_LIVE_INVESTIGATION_PLAN.md).
The owner authorized Days 13 and 14 on 19 November 2026. Implement and verify
both against their acceptance gates; do not push or proceed to Day 15 without
subsequent authorization. Keep mock defaults and distinguish source delivery
from runtime/container activation. See the milestone reports for actual outcomes.
The historical Day 6 first-execution instruction below is not a request to redo
completed milestones. Preserve current work and all historical reports.

Read the existing PROJECT_SPEC.md, CODEX_START_HERE.md, IMPLEMENTATION_BRIEF.md, architecture and Day 1–4 reports in their actual repository locations, then all six Phase 2 documents. This is an additive specification, not a replacement for Phase 1. The supplied reports describe 142 passing PostgreSQL tests and two browser tests; rerun them, do not assume they still pass. No source repository was inspected by the author of this upgrade.

## Execution contract
1. Inspect git status, branch, dependencies, routes, ORM models, migrations and tests. Preserve uncommitted work; do not reset or stash without permission. Complete Day 5 first per the original specification: QA, 16-fixture benchmark, read-only demo, documentation and deployment preparation. Report actual results; do not deploy or incur charges without authorization. Explicit posting, not auto-post, is the established behavior.
2. After a clean baseline commit, create `feature/agentic-invoice-investigation` from the current project branch. If work is dirty or baseline fails, report and resolve safely before branching. Never create another repository or alter sibling apps.
3. Implement Day 6 only on the next execution, then report and stop. Subsequent days require user direction. Each day includes a working vertical slice, regression tests, a progress report and a local commit when safe.
4. Keep Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, PostgreSQL 16, Next.js static export, n8n and existing Gemini extractor. Add LangGraph in the same backend codebase. No Redis/Celery/Kafka, no multi-tenancy, no ERP writes or payments. pgvector is optional until Day 9; check extension availability first.
5. Inspect actual package APIs and official docs before pinning dependencies. Keep existing extraction adapter untouched unless a demonstrated bug requires a change. New investigation provider is separately configurable with mock default. No credentials required for offline development.
6. AI is advisory only. Existing rule engine, revision/hash-bound operator decisions and fresh transactional posting remain authoritative. No AI tool can approve, correct, register a vendor, change policies or post. Preserve all original status transitions and database guarantees. Public demo remains synthetic/read-only, including new endpoints.
7. Report commands/results, changed files, dependency versions, test counts/skips, actual vs mocked behavior, tradeoffs, unresolved issues, next milestone, and a short teaching explanation. Never claim accuracy from scripted mocks or live tests not performed.

Read order: AGENTIC_AI_SPEC.md, AI_SYSTEM_ARCHITECTURE.md, AI_IMPLEMENTATION_ROADMAP.md, AI_EVALUATION_AND_SECURITY.md, AI_LEARNING_GUIDE.md. Proposed routes, schema and module names are contracts to reconcile with actual code, not assertions about existing implementation.
