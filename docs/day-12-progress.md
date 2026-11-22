# Day 12 — durable PostgreSQL investigation execution

Date: 18 November 2026. Branch: `feature/phase-2-days-9-12`.

This milestone was authorized together with Days 9–11. Three parallel coding agents
implemented retrieval, writer/critic and local MCP; the parent implemented and
integrated durable execution. The combined report records final regression results.

## Delivered behavior

POST `/api/v1/invoices/{id}/investigations` now commits a strict current snapshot
and returns **202 / QUEUED / execution=durable_worker**. It performs no graph/model
execution. The original invoice remains in its financial state, usually NEEDS_REVIEW.
The existing idempotency key cannot be rebound to a changed revision/read set.

A separate process of the same FastAPI backend image claims work with a short
`FOR UPDATE SKIP LOCKED` transaction. It increments attempts and a fencing generation,
leases the job and records a monotonic event. An independent heartbeat renews only
current, unexpired ownership. At most three execution attempts are allowed.

Before checkpoint access, a dedicated psycopg connection obtains a per-run session
advisory lock. The SAME connection is used by the official PostgresSaver. A new
claim can fence an old worker after lease expiry, but cannot concurrently resume its
checkpoint stream. Busy-lock claims requeue without consuming an execution attempt.
The old worker cannot publish after being fenced, cancelled or expired.

The LangGraph thread ID is the immutable run UUID. Execution checkpoints synchronously
after each superstep and resumes from persisted state, including mandatory plan,
tool cache and critic repair count. Bounded read-tool results are persisted separately
under a unique run/tool key; contradictory cached values fail closed. No Session or
financial mutation tool enters the graph. Read/model calls may repeat at some crash
boundaries; this does not claim exactly-once execution or exactly-once provider cost.

Final publication locks invoice then run. It checks current owner, generation,
unexpired lease, cancellation and the invoice revision/hash/validation batch/document/
lookup/retrieval versions before saving an advisory report. Stale or cancelled work
cannot publish an applicable result. Existing completed legacy runs remain readable.

## API and controls

- GET `/investigations/{id}`: current applicability and terminal/nonterminal status.
- GET `/invoices/{id}/investigations`: bounded offset/limit summaries.
- GET `/investigations/{id}/events?after_seq=`: bounded monotonic redacted event pages.
- POST `/investigations/{id}/cancel`: requester-only cooperative cancellation;
  immediately advances the fence, clears ownership and sets CANCELLED.
- POST `/investigations/{id}/retry`: requester-only retry of a failed current run
  with attempts remaining, resuming its existing thread/checkpoints.

All paths retain operator cookie/session authentication. Mutations require CSRF.
Integration keys grant no access. Public mode has no private queue/source routes
or database/worker execution. Financial approval/posting endpoints are unchanged.

Recognized transient execution failures requeue with exponential backoff: one second,
then two seconds, with the third failed attempt terminal. Malformed output is not
automatically treated as transient. The Day 10 draft repair loop is a separate,
checkpointed maximum of three drafts; job retry does not reset its saved count.

## Persistence and dependencies

Additive migration `0009_durable_investigation` extends investigation_runs with
ownership/availability/attempt/cancellation/event fields and creates
investigation_events and investigation_tool_results. It changes no invoice,
approval, ledger, supplier or financial-audit table. Downgrade rejects active or
cancelled jobs instead of silently coercing their history. Run the worker shutdown
and migration process deliberately; never delete volumes to test recovery.

Official `langgraph-checkpoint-postgres==3.2.1` and its resolved
`psycopg-pool==3.3.3` are pinned; existing requirement pins are unchanged. The SDK's
own tables and migrations use its supported `.setup()` lifecycle on an autocommit
connection, independent of the application Alembic chain. No custom replacement
checkpointer or Redis/Celery infrastructure was introduced.

Checkpoint serialization uses a closed registry of already-imported local contracts
and tagged JSON containers. Decoded models undergo Pydantic validation. Unsupported
types, pickle, arbitrary class names and nonfinite values are rejected. User
dictionaries cannot masquerade as type markers. No dynamic imports or hidden
chain-of-thought are stored. Checkpoints are private application data in PostgreSQL.

## Actual verification and failures

- Frozen Day 8 baseline: **282 passed, no skips**, 271.18 seconds, exit 0.
- Day 12 initial focused run: **10 passed, no skips**, 38.52 seconds. It includes
  an actual child-process termination after a saved supervisor/tool checkpoint,
  successful resume without replanning, lease fencing, per-run locking, queued/
  running cancellation, bounded transient retries, stale inputs, monotonic events
  and serializer rejection tests.
- Two additional control/retry cases: **2 passed, 10 deselected**, 8.70 seconds.
  The first run of these cases exposed a fixture that changed Invoice.updated_at
  when restoring test data; it now stales via appended evidence, without altering
  financial rows. Authentication, integration-key denial, CSRF, ownership, pagination,
  terminal/stale/exhausted retry denial and successful checkpoint retry are tested.
- First combined regression: **336 passed, 2 failed**, 406.91 seconds, exit 1.
  The failures were concurrent checkpoint setup and two missing ORM index declarations.
- Concurrent SDK setup exposed a real deadlock: a blocking advisory-lock SELECT
  held a virtual transaction while the SDK's concurrent index DDL waited for it.
  Setup now uses bounded nonblocking try-lock queries separated by idle waits.
  The concurrent request/start test then passed: **1 passed, 25 deselected**,
  14.58 seconds, exit 0.
- Added ORM declarations for the queue and evidence GIN indexes. The real schema
  comparison then passed: **1 passed, 11 deselected**, 2.04 seconds, exit 0.
- A later integration assertion initially lacked its test-only authentication import;
  corrected before the final regression run. That intermediate run had 339 passed,
  1 failed, 421.55 seconds. Final complete regression: **340 passed, no skips**,
  258.64 seconds, exit 0. All 12 durable cases passed as part of it.
- Private/public Playwright: **2 + 3 passed**, both exit 0, first attempt. Windows
  required stopping verified test-only servers after successful assertions/DB cleanup.
  Frontend type checking passed. No frontend source changes or new production build.
- Final populated-evidence demo passed through the actual checkpoint worker with
  versioned report links, stale prior reports and unchanged invoice/ledger state.
  Lint, format, dependency, staged diff and secret checks passed.

The recovery result applies to the defined synthetic test boundary, not all possible
crashes. PostgreSQL test schemas are independently generated and removed. Tests
compare financial rows before/after advisory execution. No live model, real invoice,
Slack notification, financial action, persistent workflow or production schema was
used for these failures/recovery tests.

## Files and running it

Important new files: `investigation/worker.py`, `queue.py`, `checkpoints.py`,
`controls.py`, migration `0009_durable_investigation.py`,
`tests/test_investigation_durable.py`. Existing schemas/service/routes/main/models
were integrated; `scripts/dev.py` adds a worker command; Compose adds the optional
investigation profile. Old isolated demo scripts now explicitly enqueue, run the
worker and GET the result through a disposable-schema-only helper.

```powershell
.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
.venv/Scripts/python.exe scripts/dev.py migrate
.venv/Scripts/python.exe scripts/dev.py worker --setup-only
.venv/Scripts/python.exe scripts/dev.py worker
```

For Docker, rebuild the matching backend, apply the Alembic head, and enable the
`investigation` profile as shown in README. Compose profile parsing was verified
without altering existing containers. This implementation does not claim an update
of the running local containers merely from repository changes.

The 90-second active budget and cancellation are cooperative **between nodes**;
they cannot preempt a blocking Python/provider call. Current execution is mock;
future live calls require their own transport timeout. Public deployment, live
models, UI integration and a browser-to-MCP credential broker remain outside this
batch. See [learning-day-12.md](learning-day-12.md) for code responsibilities,
data flow, trade-offs and the isolated kill/resume exercise.

Stop before Day 13.
