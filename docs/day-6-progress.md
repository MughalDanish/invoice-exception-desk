# Day 6: advisory investigation foundation

Implemented locally on 18 November 2026 (Asia/Karachi), branch
`feature/phase-2-day-6-foundation`, from clean `main` at `f23fa35`.
The older `feature/agentic-invoice-investigation` branch was preserved.
This milestone implements Day 6 only. Day 7 requires separate confirmation.

## Scope and previous milestone verification

Read the original project/implementation documents, architecture, Day 1-5 reports
and all six Phase 2 documents. The old reports are historical: the current product
already includes the frontend redesign, cookie authentication, extraction fixes
and Gmail-to-Slack integration. No new live extraction or Slack message was sent.

The frozen baseline was exported directly from `f23fa35` into ignored storage so
editing the working branch could not change files during verification. Its complete
PostgreSQL suite passed: **212 tests, no skips, exit 0**, 359.92 seconds. Existing
per-request-cookie deprecation warnings remain. This validates current software
regressions, not the accuracy of a live model.

## Delivered

- Strict, frozen Pydantic snapshots, findings, request and report contracts.
  Decimal amounts remain exact bounded strings. Unknown/missing evidence is not
  repaired or invented. Financial action enums cannot include approval or posting.
- A provider Protocol independent of extraction and a separately configured,
  mock-only provider. No Gemini key is needed or consumed by investigation.
- A real compiled LangGraph workflow: capture snapshot -> mock findings -> guarded
  advisory report. Only recorded TOTAL_MISMATCH evidence is explained. Other
  blockers produce explicit INSUFFICIENT findings. No supervisor or RAG scaffold.
- A deterministic keyed reducer rejects conflicting/duplicate task results.
  The report guard rejects missing tasks, altered numeric claims and forged
  evidence IDs. It is a deliberately narrow mock guard, not an LLM critic.
- Additive migration `0006_investigation` and `InvestigationRun` ORM mapping.
  Runs store input identity, a minimal snapshot, requester, provider/policy versions,
  status, sanitized error and report. Existing financial tables are untouched.
- Operator-cookie and CSRF protected POST
  `/api/v1/invoices/{id}/investigations`, and protected GET
  `/api/v1/investigations/{id}`. Integration keys grant no access. Public mode
  registers neither route, blocks mutation and still constructs no DB engine.
- Invoice-scoped request-key uniqueness and conflict detection on changed input.
  Identical requests return the original run; failed runs are not retried silently.
- Separate capture/publish transactions. No session or financial tool enters the
  graph. Finalization refreshes a locked invoice and rejects stale revision,
  payload hash, validation batch, source hash or eligibility. GET rechecks this
  without changing historical reports or financial audits.
- Explicitly disabled external tracing, including accidental host LangSmith
  tracing settings. No prompts, source document or provider output is logged.
- A reproducible, isolated synthetic demonstration, learning guide and updated
  README/architecture. The demo completed with the invoice response unchanged,
  zero ledger entries, and cleanup of its temporary schema.

## Files

New files:

- `backend/app/modules/investigation/{__init__,schemas,providers,graph,service,routes}.py`
- `backend/alembic/versions/0006_investigation.py`
- `backend/tests/test_investigation.py`
- `scripts/run_investigation_demo.py`
- `docs/learning-day-6.md`, `docs/day-6-progress.md`

Modified files:

- `backend/app/db/models.py`, `backend/app/main.py`, `backend/app/core/config.py`
- `backend/requirements.txt`, `.env.example`
- `backend/app/qa.py`, `scripts/dev.py`, `backend/tests/test_postgres.py`
- `README.md`, `docs/architecture.md`

No frontend application, extraction, validation, approval, posting or n8n workflow
code changed. No fixture or original invoice was rewritten.

## Engineering fixes found during verification

1. The host test runner inherited live `AI_MODE=gemini` from `.env`, invalidating
   public-mock tests. Tests now explicitly force offline modes and blank provider
   keys. A frozen-source baseline removed interference from edits during testing.
2. The first race test exposed SQLAlchemy's identity-map cache: locking a row did
   not necessarily refresh its in-memory fields with `expire_on_commit=False`.
   `populate_existing=True` now forces the final locked read to see concurrent
   validation changes. The report becomes STALE rather than appearing current.
3. The old Day 5 QA helper still passed HTTP Basic credentials after the prior
   cookie-auth upgrade. It now bootstraps a synthetic operator in its isolated
   schema and uses the real login/CSRF flow. Application auth was not weakened.
4. One full run had 237 passes and a PostgreSQL connection-timeout setup error.
   The host runner now addresses Docker PostgreSQL at `127.0.0.1`, avoiding the
   unsuccessful IPv6 localhost attempt. Short tracebacks avoid unnecessary
   connection-detail output; saved diagnostic logs were sanitized.

## Verification ledger

| Command / check | Actual result |
|---|---|
| Frozen `f23fa35` export, `python -m pytest -q --tb=short` with isolated PostgreSQL test schemas | **212 passed**, no skips, exit 0, 359.92 seconds. |
| `python scripts/dev.py test --postgres` (final serial run) | **238 passed**, no skips, exit 0, 126.27 seconds. Includes all 26 new investigation cases and the original 212 cases. 322 per-request-cookie deprecation warnings; no failed assertions. |
| `pytest tests/test_investigation.py -m "not postgres" -q --tb=short` | 17 passed, 8 PostgreSQL cases deselected at that point; exit 0. A ninth PostgreSQL case was subsequently added and included in the final full suite. |
| Original targeted graph/migration run | 26 passed, 1 failed: caught stale SQLAlchemy identity-map data. Fixed and covered in the final full suite. |
| Earlier mutable-source/live-env attempt | 173 passed, 4 failed, 35 setup errors. This was not a valid baseline: live test configuration and concurrently edited migration sources interfered. Replaced by the frozen-source baseline above. |
| Earlier full updated run | 237 passed, 1 PostgreSQL connection-timeout setup error. Final serial numeric-loopback run passed all 238. |
| `python scripts/run_investigation_demo.py` | Exit 0: synthetic wrong-total invoice produced a COMPLETED mock advisory report; invoice detail unchanged; ledger empty; test schema removed. |
| `python -m app.qa benchmark --output storage/day-6-phase-1-benchmark.json` (absolute output path, host TEST_DATABASE_URL) | **16/16 contracts passed**, exit 0. Workflow TP 11 / FP 0 / FN 0 / TN 5; rule subset 14 cases, TP 9 / FP 0 / FN 0 / TN 5. Synthetic mock p50 291.969 ms / p95 924.509 ms. Original committed benchmark artifacts unchanged. |
| `npm.cmd run typecheck` | Passed, exit 0. No frontend application changes. |
| `npm.cmd run test:e2e` (operator rerun) | **2 passed**, 2.1 minutes; Playwright `.last-run.json` reports passed with no failed tests. The PowerShell redirection wrapper returned 1 after converting routine stderr into NativeCommandError; no test assertion failed on this rerun. |
| `npm.cmd run test:e2e -- --config playwright.public.config.ts` (subprocess captures actual exit) | **3 passed**, exit 0, 1.1 minutes. Public immutability/mobile, missing/untrusted evidence and loading/offline/error recovery. |
| `python -m pip check` | Passed, exit 0; no broken requirements. |
| Ruff check and format check on changed Python modules/tests/scripts | Passed, exit 0. |
| `git diff --check` and protected-path diff against `f23fa35` | Passed; extraction, financial rules, approvals, posting, n8n, fixtures and frontend source unchanged. |

The first operator Playwright run passed the mobile case and failed the desktop
case while waiting for invoice details (the page still showed its loading state).
No assertion was loosened; the rerun passed both cases with unchanged test code.

## Dependency and architectural decisions

Pinned LangGraph **1.2.22** after checking official StateGraph documentation and
running pip resolution against the complete existing requirements. The resolver
added 19 packages without changing existing pins. These include langchain-core
1.8.2, langgraph-checkpoint 4.3.2, langgraph-sdk 0.4.14 and langsmith 0.15.0.
The latter packages are transitive requirements, not enabled hosted services.
`pip check` passed. Python tested locally: 3.12.10.

Do not confuse the installed checkpoint library with implemented persistence of
graph execution: no checkpointer is configured. Runs and reports persist in
PostgreSQL, but execution itself is not durably resumable.

The stronger unique `(invoice_id, idempotency_key)` scope rejects changed inputs
even across revisions/batches. It is simpler than silently creating another run
when a client reuses a key. Future worker state/event tables are intentionally
not pre-created. The existing modular monolith and static-export frontend remain.

## Limits and next milestone

- Scripted mock only. Live investigation reasoning, accuracy, token usage, cost,
  retrieval recall and production latency metrics are **NOT RUN**.
- No document reading, supplier lookup/history, PO/receipt corpus, vector search,
  critic, MCP, model routing, investigation screen or external tracing.
- 202 responses explicitly identify `execution=synchronous_local`. This bounded
  three-node mock runs within the request. There is no background worker, durable
  checkpoint recovery, cancellation or retry endpoint; interrupted RUNNING rows
  cannot resume yet. These are later milestones, not hidden capabilities.
- Reports cite stored validation IDs. Evidence browsing/versioned retrieval and
  public seeded investigation reports are not implemented. Public routes expose
  no private report or trace.
- A report does not approve anything, prove authenticity, recalculate a total or
  determine that a document discrepancy was definitely the supplier's mistake.
- The running local application containers are not upgraded by source-code tests.
  README provides the additive migration/build/start commands for local adoption.
  No new Linux image or frontend production build was run in this backend milestone.
- No remote push, merge to dev/main, cloud provisioning or paid call was performed
  for this milestone. Phase 1 data and running containers were preserved.

Next, only after review: **Day 7 supervisor, mandatory blocker routing and read-only
tools**, with malformed-plan and skipped-task safety tests.

## Learning handoff

Read [the Day 6 learning guide](learning-day-6.md) alongside `graph.py` and
`service.py`. It explains graph versus agent, TypedDict versus runtime validation,
the provider Protocol, deterministic reducers, idempotency, transaction boundaries,
the stale identity-map bug, source grounding and an owner exercise.

Run `.venv/Scripts/python.exe scripts/run_investigation_demo.py` and inspect the
synthetic report in ignored storage. Its temporary IDs cannot be queried after
cleanup. The example demonstrates safe execution, not independent AI accuracy.
