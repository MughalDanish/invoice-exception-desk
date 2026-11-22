# Days 13 and 14 integration handoff

19 November 2026. Branch: `feature/phase-2-days-13-14`.
Status: one live investigation accepted by deterministic validation and semantic
critic, with zero repairs. See [latest results and grounding fixes](investigation-verification-2026-11-19.md).
Broader synthetic-pair and full-regression verification gaps remain open.

## Delivered behavior

An operator can start an advisory investigation from invoice detail, follow its
persisted progress, cancel/retry when authorized, and inspect findings, exact
assertions, uncertainties and versioned supporting evidence. The UI uses the
existing shadcn components, TanStack Query, cookie authentication and Theme B.
Public mode does not mount investigation request hooks or controls.

The opt-in live graph uses the configured Gemini model. It starts with recorded
rule evidence as a deterministic anchor, then exposes the full authorized tool
set for model-selected follow-up. An official MCP client executes those requests
through a local stdio child serving the frozen invoice scope. No arbitrary SQL,
URLs, paths or financial mutation tools are provided. The scripted graph remains
available for offline development and tests.

A separate structured writer and model critic cannot bypass the programmatic
schema, delivered-evidence, exact-value/currency, scope or freshness gates.
Authentication is checked before and after boundaries and before publication.
The PostgreSQL worker retains leases, fencing and checkpoints; durable call
reservations prevent retries from resetting the run budget.

## Verification

- Frozen previous milestone `f8b838f`: 340 backend tests passed, exit 0.
- Frontend: 43 unit tests, typecheck, targeted ESLint and production build passed.
- Public browser suite: 3 passed, exit 0.
- Private browser suite in a quiet window: 3 passed, exit 0. Earlier attempts and
  a later cold-login focused failure are preserved in the Day 14 report.
- Windows full current backend: 392 passed, four failed, five PostgreSQL-recovery
  setup errors, exit 1. All four failed cases passed after the two small fixes
  and targeted rerun. This is not a passing full regression.
- Final presentation-only suite: one passed, exit 0, at all four widths.
- Full Linux-image regression and successful live synthetic pair: pending.

## Runtime update

The existing PostgreSQL database was backed up in custom format before the
additive `0010_live_investigation` migration. The archive table of contents was
readable. Frontend/backend/worker were rebuilt and started; existing PostgreSQL,
invoice-file and n8n volumes were preserved. Final image refresh follows any
verification fixes. No remote push or Day 15 implementation is included.

## Engineering concepts

The provider is an adapter for one model request; the graph owns orchestration
and the host owns authority. A model tool call is untrusted input, not executable
application code. MCP standardizes the transport without granting permission.
An immutable evidence snapshot makes a resumed investigation internally
consistent; revision checks prevent an old report being presented as current.
Exact assertions make some factual claims verifiable in code, while semantic
support still requires probabilistic critique and human review.

## Limits and next step

No accuracy benchmark, universal prompt-injection resistance, document
authenticity, exact billing cap or exactly-once external model execution is
claimed. The same model generates and critiques, so correlated errors remain
possible. Retrieval is bounded SQL/full-text evidence, not deployed pgvector
semantic search. Day 15 remains the held-out evaluation/observability milestone
and requires separate owner authorization.

See [Day 13 details](day-13-progress.md), [Day 14 details](day-14-progress.md),
[backend learning guide](learning-day-13.md) and [UI learning guide](learning-day-14.md).

## Files included

- `README.md`
- `backend/alembic/versions/0010_live_investigation.py`
- `backend/app/core/config.py`
- `backend/app/db/models.py`
- `backend/app/main.py`
- `backend/app/modules/investigation/budgets.py`
- `backend/app/modules/investigation/checkpoints.py`
- `backend/app/modules/investigation/controls.py`
- `backend/app/modules/investigation/delegation.py`
- `backend/app/modules/investigation/gemini_provider.py`
- `backend/app/modules/investigation/live_graph.py`
- `backend/app/modules/investigation/live_policy.py`
- `backend/app/modules/investigation/live_schemas.py`
- `backend/app/modules/investigation/mcp_adapter.py`
- `backend/app/modules/investigation/mcp_client.py`
- `backend/app/modules/investigation/mcp_stdio.py`
- `backend/app/modules/investigation/queue.py`
- `backend/app/modules/investigation/routes.py`
- `backend/app/modules/investigation/schemas.py`
- `backend/app/modules/investigation/service.py`
- `backend/app/modules/investigation/tools.py`
- `backend/app/modules/investigation/worker.py`
- `backend/requirements.txt`
- `backend/tests/test_investigation_gemini.py`
- `backend/tests/test_investigation_injection.py`
- `backend/tests/test_investigation_live.py`
- `backend/tests/test_investigation_live_documents.py`
- `backend/tests/test_investigation_live_mcp.py`
- `backend/tests/test_investigation_live_migration.py`
- `backend/tests/test_investigation_live_recovery.py`
- `backend/tests/test_investigation_tool_contract.py`
- `backend/tests/test_postgres.py`
- `docker-compose.yml`
- `docs/architecture.md`
- `docs/day-13-progress.md`
- `docs/day-14-progress.md`
- `docs/days-13-14-progress.md`
- `docs/learning-day-13.md`
- `docs/learning-day-14.md`
- `docs/phase-2/AGENTIC_AI_SPEC.md`
- `docs/phase-2/AI_EVALUATION_AND_SECURITY.md`
- `docs/phase-2/AI_IMPLEMENTATION_ROADMAP.md`
- `docs/phase-2/AI_LEARNING_GUIDE.md`
- `docs/phase-2/AI_SYSTEM_ARCHITECTURE.md`
- `docs/phase-2/AI_UPGRADE_START_HERE.md`
- `docs/phase-2/DAY_13_LIVE_INVESTIGATION_PLAN.md`
- `fixtures/investigation/prompt-injection-cases.json`
- `frontend/playwright.visual.config.ts`
- `frontend/public-tests/public.spec.ts`
- `frontend/src/app/globals.css`
- `frontend/src/components/invoice-detail.tsx`
- `frontend/src/features/investigations/api.ts`
- `frontend/src/features/investigations/investigation-panel.tsx`
- `frontend/src/features/investigations/presentation.ts`
- `frontend/src/features/investigations/queries.ts`
- `frontend/src/features/investigations/types.ts`
- `frontend/tests/investigations.spec.ts`
- `frontend/unit-tests/investigations.spec.ts`
- `frontend/visual-tests/investigation.spec.ts`
- `scripts/dev.py`
- `scripts/run_live_investigation_smoke.py`

## Manual review

Open http://localhost:3000 (or http://127.0.0.1:3000), sign in with the existing
operator account, and open an invoice in Needs review with current validation.
Select Investigation. Starting a run does not approve, correct or post anything.
The run survives page reload; active states poll, while terminal states stop.
Inspect mode, findings, recorded assertions, recommendations, uncertainties,
source versions and the expandable timeline/technical payload. Change invoice
fields only through the existing review flow; an older investigation must become
stale. Public demo mode must expose no private investigation controls or requests.

Screenshots under `storage/day-14-report-fixture-{1440,1024,768,390}.png` are
explicit presentation fixtures. They are not live Gemini results. The PDF iframe
may be blank in headless Chromium captures; the original file remains available.
