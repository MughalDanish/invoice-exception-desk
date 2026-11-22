# Phase 2 Days 9–12 — integration handoff

Date: 18 November 2026. Branch: `feature/phase-2-days-9-12`.
Baseline: `1775844` (Day 8). Scope: Days 9, 10, 11 and 12 only.

## Functionality

| Milestone | Implemented | Boundary |
|---|---|---|
| Day 9 | Exact scoped SQL, PostgreSQL FTS, deterministic RRF, immutable version/hash citations and authenticated evidence links | Lexical retrieval; no pgvector/embeddings available |
| Day 10 | Structured resolution writer, deterministic critic gate, optional provider critic, at most two repairs, safe human-evidence escalation | Scripted mock; no arbitrary financial recommendations or writes |
| Day 11 | Local MCP JSON-RPC stdio initialization, ping, tools/list and read-only calls, existing JWT/session checks | Deliberate protocol subset; no public listener or browser credential broker |
| Day 12 | Durable queue, official PostgreSQL checkpoints, heartbeat/leases, fencing, per-run locking, cancellation/retry and event polling | Same monolith/image, no Redis/Celery; cooperative per-step limits |

Three parallel agents worked on separate retrieval, writer/critic and MCP files.
The parent implemented durable execution, integrated the shared contracts and
ran the combined verification. Dependencies were resolved before integration;
parallel coding did not bypass the final shared regression suite.

Investigation POST now returns immediately after committing QUEUED work. It does
not execute the graph. Poll the run endpoint; an optional worker process resumes
its persisted graph. Invoice financial status remains independent. The worker can
save only advisory investigation metadata/reports, never approve suppliers,
correct invoices, approve financial records or post to the ledger.

Reports expose structured citations plus exact relative `evidence_links` generated
from their source versions. A deterministic guard rejects links that do not match
the captured citations. The original upload/extraction/validation/review/posting,
cookie authentication and n8n integration contracts remain unchanged.

## Verification

Final complete backend regression: `.venv/Scripts/python.exe scripts/dev.py test --postgres`
returned **exit 0, 340 passed, no skips, 258.64 seconds**. The 472 warnings are
existing-style Starlette per-request-cookie deprecations in test helpers. Financial,
authentication, public-mode, retrieval, critic, MCP and durable execution tests all
passed. The source was unchanged during this final successful run.

Private Playwright acceptance: **2 passed, exit 0**, 4.8 minutes including Windows
cleanup. Public acceptance: **3 passed, exit 0**, 2.5 minutes. All five passed their
first attempt; no test retry. Both runners needed termination of only verified
owned API/Next.js test processes after successful assertions/schema cleanup because
Windows teardown stalled. No live application containers were stopped.

`npm.cmd run typecheck`: **exit 0**. Ruff lint/format, `pip check`, staged diff and
secret checks passed. Compose's optional worker profile parsed successfully without
changing services. No production frontend build was rerun because frontend source
is unchanged; the browser suite exercised the financial UI against the new backend.

All counts are actual execution results, not aspirational evaluation targets.

- Frozen Day 8 baseline: **282 passed**, no skips, exit 0, 271.18 seconds.
- Day 9 focused: **6 passed**, exit 0, actual PostgreSQL.
- Day 10 focused: **15 passed**, exit 0.
- Day 11 unit: **23 passed**; its two PostgreSQL session cases are included in the
  combined suite rather than counted as locally run in the initial unit command.
- Day 12 focused: **10 passed**, then **2 additional control cases passed**.
- Existing Day 6, 7 and 8 demos adapted to explicit durable execution: all exit 0;
  invoice responses/empty ledgers unchanged and disposable schemas removed. A final
  populated-evidence demo also passed after integrating serialized evidence links.
- First combined run: **336 passed, 2 failed**. A checkpoint setup/index deadlock
  and missing ORM index declarations were fixed. Their focused reruns passed.
- The second combined run returned **339 passed, 1 failed**, 421.55 seconds; a new
  evidence-link assertion lacked its test-only auth import. Corrected that import
  before the final clean run. Detailed failures and recovery tests are in Day 12's report.

Day 9 development retrieval comparison: three scenarios, nine synthetic source
texts, six relevant sources. Exact SQL recall@5 **0.50**, FTS **1.00**, RRF **1.00**.
There are at most three sources per scenario, so this is not a challenging top-five
ranking benchmark; no fusion improvement over FTS or live model quality is claimed.
The vector extension was unavailable. Larger held-out evaluation remains Day 15.

## Changes and review entry points

- `backend/app/modules/evidence/`: strict provenance, scoped SQL/FTS/RRF and source resolver.
- `backend/app/modules/investigation/graph.py`, `resolution.py`, `resolution_schemas.py`:
  verified findings → bounded writer/critic → advisory report.
- `investigation/mcp_adapter.py`, `scripts/run_mcp_stdio.py`: local authenticated read tools.
- `investigation/queue.py`, `checkpoints.py`, `worker.py`, `controls.py`: durable execution.
- Shared schemas/service/routes/main/models: retrieval/link binding, queue API,
  metadata, private routing and current migration checks.
- Migrations `0008_evidence_search` and `0009_durable_investigation`: additive search
  index and advisory queue tables/fields; financial tables untouched.
- `backend/requirements.txt`: two official pinned checkpoint dependencies only.
- `backend/tests/test_evidence_retrieval.py`, `test_investigation_resolution.py`,
  `test_investigation_mcp.py`, `test_investigation_durable.py`: new safety/reliability tests.
- Existing investigation tests/demo helpers: explicitly drain worker in isolated tests;
  the application HTTP API stays asynchronous.
- `docker-compose.yml`, `scripts/dev.py`: optional worker process and host wrapper.
- Separate synthetic retrieval fixture/evaluation script, README and architecture.
- Per-day progress/learning: [Day 9](day-9-progress.md) ? [guide](learning-day-9.md);
  [Day 10](day-10-progress.md) ? [guide](learning-day-10.md);
  [Day 11](day-11-progress.md) ? [guide](learning-day-11.md);
  [Day 12](day-12-progress.md) ? [guide](learning-day-12.md).

## Manual review

Read the per-day learning guides and run the isolated synthetic demonstrations:

```powershell
.venv/Scripts/python.exe scripts/run_retrieval_evaluation.py
.venv/Scripts/python.exe scripts/run_parallel_demo.py
.venv/Scripts/python.exe scripts/dev.py test --postgres
```

The evaluation/report JSON files remain in ignored `storage/`. The parallel demo
uses a disposable database schema, explicitly enqueues and runs its own worker,
and verifies missing/populated evidence and stale reports. Do not seed its invented
supporting texts into real invoices.

To activate this code locally, follow the README migration and worker commands.
Existing containers do not read changed source files automatically. This batch
does not claim live local migration/container deployment or remote publication.

## Limits and next work

The application remains a FastAPI modular monolith and Next.js static-export frontend.
No frontend source, original invoice fixtures, financial rules, approvals/posting
service or n8n workflow was modified. No live model calls, messages, new cloud
infrastructure or payment integrations were invoked.

The critic uses deliberately finite canonical mock output, not semantic correctness
certification. Citation integrity is provenance, not proof of source truth. The MCP
launcher needs a trusted local host to supply an ephemeral existing access token;
it never mints a different permission or persists credentials. Checkpoints are
private data; closed serialization prevents arbitrary object revival but does not
make a compromised database authoritative. Worker limits/cancellation are cooperative
between graph nodes; future live providers need their own network timeouts.

Day 13 budgets/model routing, Day 14 investigation UI/security integration, Day 15
larger evaluation/tracing and Day 16 packaging remain. Stop before Day 13 until
the owner approves it.
