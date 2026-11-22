# Day 8 — parallel investigators and synthetic supporting evidence

Date: 18 November 2026. Branch: `feature/phase-2-day-8-investigators`.

## Previous milestone and publication

Baseline `1d3b7d6` contains Day 6 (`a5195b4`) and Day 7 (`1d3b7d6`). Its recorded
backend regression result was 268 passed, no skips; private/public browser checks
passed after one documented private timing retry. The latest source was inspected
against the roadmap before implementation. Day 6–7 code was pushed successfully
to `origin/feature/phase-2-day-6-foundation`; main/dev were not merged or rewritten.

Day 6 established strict snapshot-bound advisory runs, the run migration, operator
API routes, idempotency and stale-result suppression. Day 7 added mandatory
supervisor plans and read-only exact lookups for arithmetic, duplicate invoices,
supplier approval and threshold outliers. Both use offline scripted mock providers.

Initial push and Docker build failed because GitHub and Docker Hub DNS resolution
failed. Resolution recovered; the push and build were retried. Existing services
were kept running during the build. Dependency installation was needed once because
Day 6 changed the pinned requirements; Day 8 adds no dependency.

## Implemented behavior

- Financial, supplier and document nodes fan out in one LangGraph superstep.
  An explicit AND join waits for all three, including no-op roles.
- Plans still cannot omit or alter mandatory blocker work. New snapshots also
  require a supporting-document inventory task. Legacy snapshots remain readable.
- Tools execute once before fan-out over frozen input. No worker receives a
  Session, path, SQL, network client or financial write capability. Service
  configuration caps graph concurrency at three.
- Finding merge is keyed, sorted, bounded and idempotent for identical updates;
  conflicting updates fail closed. The bound is 64 blockers plus one document task.
- Additive migration `0007_investigation_documents` creates only an evidence table
  and UPDATE/DELETE protection trigger. Source UUID/version retain historical text.
- Supporting source capture filters by invoice UUID AND normalized supplier, picks
  latest versions, captures at most 12 sources and reports truncation. Frozen
  validation checks source scope, duplicates and canonical text digests.
- Evidence additions/visible new versions stale prior reports on GET and finalization.
  Stored historical reports remain unchanged. Missing PO/receipt/email is explicit.
- A separate four-text synthetic corpus includes PO, receipt, conflicting email
  and malicious email instructions. Only the disposable demo imports it.

The document mock inventories source kinds and always returns `INSUFFICIENT` for
reconciliation. Presence of documents does not establish their truth. It does not
repeat injected instructions, infer monetary values, resolve discrepancies, approve
suppliers or authorize posting. No real invoice evidence was imported or modified.

## Verification

Final complete backend regression: `.venv/Scripts/python.exe scripts/dev.py test --postgres`
returned **exit 0, 281 passed, no skips**, 433.73 seconds, with 373 existing-style
Starlette per-request-cookie deprecation warnings. This includes real isolated
PostgreSQL migrations/round trips, financial workflows, authentication/public-mode
regressions and the Day 8 integration tests. Concurrent Docker compilation increased
runtime; this is not a benchmark.

After that run started, report verification was changed to reuse captured tool
results instead of re-invoking tools. A new actual-call-count test was added. The
final investigation-focused run returned **exit 0, 46 passed, 24 PostgreSQL cases
deselected**, 2.77 seconds. The full run therefore predates this narrow cache-reuse
change; it must not be described as 282 full-suite tests. The final focused run
covers the change, strict output gates, merge behavior and routing.

The final full suite passed before applying migrations to the running application.
Runtime migration and container checks are recorded below.

### Local container handoff

- `docker compose build backend frontend`: exit 0; frontend production compilation,
  TypeScript checking and static export completed. No frontend source changes.
- A final `docker compose build backend`: exit 0; dependency-install layer was
  **CACHED**, and final source changes were copied into the image.
- PostgreSQL `public` schema backed up before migration to ignored
  `backups/pre-phase2-day8-public.dump` (60,384 bytes). No volume was removed.
- `docker compose run --rm --no-deps backend python -m alembic upgrade head`:
  exit 0, applied `0005_cookie_auth` ? `0006_investigation` ?
  `0007_investigation_documents`.
- `docker compose --profile dashboard --profile automation up -d --wait --no-build`:
  exit 0. Backend/frontend recreated with latest images. Existing PostgreSQL and
  n8n containers/volumes retained; workflow, credentials and encryption key untouched.
- `alembic current` inside the running backend: `0007_investigation_documents (head)`.
- Running-container SHA-256 hashes for `main.py`, `graph.py` and `service.py` exactly
  match the final workspace files.
- HTTP checks: backend `/health` **200**, dashboard **200**, n8n `/healthz` **200**;
  unauthenticated invoices and investigation reads **401**. Credentialed CORS for
  `http://127.0.0.1:3000` passed.
- Docker emitted a Windows Git provenance warning; the builds still passed.
  Runtime file-hash comparison verifies source identity independently.

Review the dashboard at `http://127.0.0.1:3000` and n8n at
`http://localhost:5678`. The Phase 2 investigation UI is not implemented yet; use
existing authenticated API routes or the isolated demo to review Day 8 behavior.

The first complete backend run returned exit 1: **276 passed, 4 failed**, no skips,
209.00 seconds. Failures and fixes:

1. The failure-replay test counted both parallel task calls as retries. It now
   records task IDs, rejects duplicate task execution, and verifies that replay
   adds no calls.
2. The new cross-invoice fixture supplied a nonexistent Invoice idempotency field.
   Removed that invalid fixture argument.
3. A policy-race test toggled approval once per worker, allowing two changes to
   restore the starting value. It now makes an idempotent persistent policy change
   and verifies stale publication rejection.
4. The migration round-trip test expected the old head. Updated its expected head.

An earlier focused non-DB pass had 45 passed and 23 PostgreSQL skips because no test
database URL was provided. This is not the full regression result. The sequential
completion-order assertion was updated to assert supervisor-before-workers and
all-workers-before-report instead. The dedicated timed barrier test proves overlap.

Measured three-branch overlap in a standalone run: **0.050651 seconds**; exit 0,
1 passed and 11 deselected at that point (before two later tests were added). This is a test measurement, not an SLO.

The isolated demo returned exit 0: missing and populated source inventories both
completed; adding evidence made the previous report stale; original invoice detail
and empty ledger were preserved; the disposable schema was removed. Output is
ignored `storage/day-8-synthetic-reports.json`.

Lint, formatting checks, `pip check` and frontend `npm.cmd run typecheck` passed.
Detailed command logs and dumps stay in ignored storage/backups, not Git.

## Changed files

- `backend/app/modules/investigation/graph.py`: parallel branches, shared pre-capture,
  explicit join, deterministic merge and missing evidence report.
- `schemas.py`: immutable document contracts, scope/integrity validation and bounds.
- `routing.py`: mandatory inventory task for new snapshots.
- `tools.py`: sixth read-only tool for source-kind inventory.
- `providers.py`: strict scripted document finding and per-task verification.
- `documents.py`: new bounded latest-version scoped SQL capture.
- `service.py`: document snapshot, freshness checks, version metadata, concurrency cap.
- `backend/app/db/models.py`: evidence ORM model.
- `backend/alembic/versions/0007_investigation_documents.py`: additive table/trigger.
- `backend/app/main.py`: require current migration head for health.
- `backend/tests/test_investigation_parallel.py`: overlap, deterministic merge,
  missing/hostile/conflicting evidence, scope/hash checks, bounds, latest versions,
  stale reports, concurrent evidence changes and immutable source rows.
- `backend/tests/test_investigation.py`: parallel task failure/replay assertion.
- `backend/tests/test_investigation_routing.py`: parallel order and policy-race tests.
- `backend/tests/test_postgres.py`: expected migration head.
- `fixtures/investigation/day-8-corpus.json`: separate synthetic supporting corpus.
- `scripts/run_parallel_demo.py`: isolated, authenticated mock demonstration.
- `README.md`, `docs/architecture.md`, this report, `docs/learning-day-8.md`:
  current behavior, limits, commands and engineering concepts. README's stale Basic
  Auth description was also corrected to reflect existing cookie authentication.

## Scope and limitations

No extraction, deterministic financial rules, authorization, review/posting service,
n8n workflow or frontend source was changed. Original invoice fixtures are untouched.
The application remains a FastAPI modular monolith. No new infrastructure, live
model calls, external traces or notifications were introduced.

Execution is bounded synchronous local mock work, not durable/background execution.
There is no document upload/linking API, real supporting-mail import, document text
reconciliation, hybrid search, evidence-link endpoint, writer/critic or investigation
UI. Source content is retained in immutable run snapshots; public mode exposes none
of it. Sources outside a truncated capture are not tracked individually. Database
administrator changes remain outside ordinary trigger protections.

Frontend source is unchanged. Browser acceptance results from Day 7 are historical;
they must not be represented as a fresh Day 8 browser run.

## Reproduce and learn

```powershell
.venv/Scripts/python.exe scripts/dev.py test --postgres
.venv/Scripts/python.exe scripts/run_parallel_demo.py
.venv/Scripts/python.exe -m pytest backend/tests/test_investigation_parallel.py -k overlap -s -q
```

Read [the Day 8 learning guide](learning-day-8.md) for reducer semantics, fan-in,
session safety, source versioning, data flow, independent modification points and
the exercise. Review the synthetic report JSON locally. Production invoices without
linked evidence should report missing sources, not acquire invented corpus values.

Stop after Day 8. Day 9 (hybrid retrieval and evidence links) needs owner confirmation.
