# Day 12: durable investigation execution

The API now captures an immutable invoice/evidence snapshot and returns a **202 QUEUED** response. A separate worker process runs the existing investigation graph. Both processes belong to the same FastAPI modular monolith and use PostgreSQL; there is no message broker or new microservice.

## Read the implementation in this order

| File | Responsibility |
| --- | --- |
| `backend/app/modules/investigation/service.py` | Capture a scoped snapshot, enqueue idempotently, check report applicability on read. |
| `backend/app/modules/investigation/queue.py` | Claim work, heartbeat leases, validate ownership and append sequenced redacted events. |
| `backend/app/modules/investigation/worker.py` | Hold the per-run lock, execute/resume graph supersteps, cache tool results and publish only while authorized. |
| `backend/app/modules/investigation/checkpoints.py` | Official `PostgresSaver` lifecycle, dedicated database connection and closed JSON serialization. |
| `backend/app/modules/investigation/controls.py` | Operator cancellation/retry, paginated run lists and event timelines. |
| `backend/app/modules/investigation/graph.py` | Parallel investigators, writer/critic attempts and optional checkpointer. |
| `backend/alembic/versions/0009_durable_investigation.py` | Additive queue ownership columns, event records and read-tool result records. |
| `backend/tests/test_investigation_durable.py` | Real PostgreSQL failure/recovery, fencing, cancellation and serializer tests. |
| `scripts/dev.py` | Load local configuration and run migration/worker/test commands without printing secrets. |
| `docker-compose.yml` | Optional `investigation` profile running the worker from the same backend image. |

## A job row and a checkpoint solve different problems

`investigation_runs` records whether work is queued, who currently owns it, when its lease expires, how many attempts have occurred and whether the report is applicable. This is the **job lifecycle**.

LangGraph checkpoints store the graph's validated state and which nodes run next. This is the **execution position**. A process can die after the supervisor and resume at the parallel workers rather than planning again. The official PostgreSQL saver manages its own checkpoint tables; application events and tool-result records remain separate.

The run UUID becomes the stable graph `thread_id`. Never generate a new thread ID on every retry: that would start another execution instead of recovering the saved one.

## Follow one request

1. `start_investigation` locks the invoice, validates its current revision and captures rules, lookups, documents and retrieval results. The same invoice/idempotency key returns the existing matching run; changed inputs produce a conflict.
2. It inserts a `QUEUED` job and event, commits and returns. The request does not run model work.
3. `claim_next` selects eligible work with `FOR UPDATE SKIP LOCKED`. Competing workers skip a row already being claimed instead of waiting for each other.
4. The short claim transaction assigns an owner, advances a monotonically increasing fencing generation, increments attempts and gives the worker a lease using PostgreSQL's clock.
5. `execute_claim` opens a dedicated connection and tries a session advisory lock derived from the run ID. **That same connection performs checkpoint reads/writes.**
6. The worker validates ownership, resumes the saved graph state or starts a new one, then invokes one graph superstep at a time with synchronous checkpoint persistence and interruption after each step.
7. `save_step` validates the claim again, stores immutable read-tool results and appends a redacted checkpoint event. A heartbeat thread renews the lease in short separate transactions.
8. `finish` locks the invoice and run, rechecks the owner, fence, lease, cancellation and current source snapshot, then publishes an advisory report or marks the result stale. It never approves an invoice or posts a ledger entry.

The expensive graph work does not hold an invoice row lock or an open financial transaction.

## Lease, heartbeat, fence and lock are complementary

A **lease** permits recovery if a worker disappears. A **heartbeat** extends a live worker's lease. A **fence** prevents an old worker from publishing after a newer claim has taken ownership. Checking only the owner's name is insufficient because the same process identity can be reused.

A lease alone cannot prevent two processes from touching the same checkpoint stream: an old worker could still be finishing a node when its lease expires. The per-run **session advisory lock** serializes checkpoint access. The worker must hold the lock on the saver connection itself; using an unrelated connection would allow its saver to keep writing after the lock connection was lost.

If another execution still holds that lock, the new claim is requeued briefly without consuming an execution attempt. The previous worker remains fenced from publishing. When a process is killed, PostgreSQL closes its connection and releases its session lock.

## Why this does not mean exactly once

Suppose a provider call returns, then the process dies before its result is durably checkpointed. Recovery may repeat that call. Checkpointing provides resumable execution, not a guarantee that every call occurred once. Any future live provider must tolerate repeat calls and report their possible cost. Financial writes are excluded from this graph entirely.

Persisted read-tool results have unique run/tool keys. Identical results can be reused; conflicting contents fail closed. This helps deduplicate reads but does not turn external effects into exactly-once transactions.

## Safe checkpoint serialization

Study `SafeCheckpointSerializer`. It writes tagged JSON containers and recognizes only model classes already registered from the application's evidence/investigation schema modules. It does not load pickle, import a class named by stored input or execute a serialization hook supplied by a document.

UUIDs, datetimes, bytes and containers have explicit encodings. Pydantic models are reconstructed through their strict validation boundary. A dictionary containing a type-looking key remains ordinary data. Unknown types, unknown encoding labels, non-finite numbers and oversized checkpoint payloads are rejected.

This is safer than broadly deserializing arbitrary Python objects, with a maintenance cost: new graph state types must be explicitly supported and tested. A code upgrade that changes stored contracts needs a checkpoint compatibility decision; do not silently reinterpret old state.

## Cancellation, retries and stale evidence

Cancellation is cooperative. The requesting operator can cancel queued/running jobs; the API advances the fence and clears ownership. A node already executing may finish, but ownership checks prevent its report from publishing. Cancellation is not a way to interrupt an arbitrary Python function instantly.

Recognized transient execution failures are requeued with bounded exponential backoff. There are at most three worker attempts; malformed output is not automatically classified as transient. The Day 10 writer's three draft attempts are a separate graph-level policy, and its counter is checkpointed. Manual retry also requires remaining attempts and a current snapshot.

Invoice corrections, a changed validation batch or changed captured supporting evidence make a report stale. A stale report is hidden from current applicability while historical stored data remains intact. The operator starts a new run for new evidence.

The worker's 90-second active execution limit is checked **between graph steps**. It is a cooperative budget, not a hard timeout on a provider call that blocks inside a node. Current execution is scripted mock; a future live provider also needs its own explicit network/request timeouts.

## Commands and an isolated recovery exercise

From the repository root, with local PostgreSQL running and the existing `.env` configured:

```powershell
.venv/Scripts/python.exe scripts/dev.py migrate
.venv/Scripts/python.exe scripts/dev.py worker --setup-only
.venv/Scripts/python.exe scripts/dev.py worker --once
```

`--setup-only` initializes the supported saver schema. `--once` claims at most one eligible job; it does not enqueue an invoice. Without those flags the worker polls for work. The local wrapper forces investigation mock mode and blanks extraction provider keys for worker execution.

For the optional Compose process after building the matching backend image and applying migrations:

```powershell
docker compose --profile investigation up -d investigation-worker
docker compose logs --tail 100 investigation-worker
```

Do not delete database volumes to test recovery. Use the isolated integration tests:

```powershell
.venv/Scripts/python.exe scripts/dev.py test --postgres
```

Study `test_killed_child_resumes_persisted_checkpoint_without_replanning`. It creates synthetic data in a random test schema, starts a real child worker and waits for its persisted supervisor/tool checkpoint. It terminates that child, expires only that test run's lease, then resumes with a provider whose `plan` method fails if called again. It checks completion, unchanged tool results and unchanged financial state. The test cleanup removes only its generated schema.

Exercise: draw the ownership timeline for the killed child, the expired lease and the second claim. Explain why the second fence is larger, why the checkpoint resumes without replanning, and why the test does not establish exactly-once provider calls at every possible crash point. Then inspect the late-publication and cancellation tests and identify the checks that reject the original worker.

## Trade-offs to remember

PostgreSQL keeps queue ownership, events and checkpoints close to the existing application and avoids unnecessary infrastructure. Dedicated lock/saver connections consume database connections per active run; concurrency must remain bounded. Polling is simpler than an event bus but introduces a small scheduling delay. The current provider remains mock, so successful recovery tests demonstrate execution reliability rather than live model accuracy or financial correctness.
