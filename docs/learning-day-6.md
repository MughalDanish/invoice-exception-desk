# Day 6 learning guide: a safe first investigation graph

This is an offline foundation, not autonomous financial decision-making. Trace the
working example with `.venv/Scripts/python.exe scripts/run_investigation_demo.py`.
Open `storage/day-6-synthetic-report.json` afterwards. IDs are from a temporary
synthetic database removed when the command finishes; they are not live API links.

## Files and responsibilities

| File | Responsibility |
|---|---|
| `backend/app/modules/investigation/schemas.py` | Frozen strict Pydantic contracts, bounded strings/collections, exact amount strings and advisory action allowlist. |
| `backend/app/modules/investigation/providers.py` | Provider Protocol and scripted mock. Explains only recorded total evidence; abstains for unsupported/missing evidence. |
| `backend/app/modules/investigation/graph.py` | Typed graph state, keyed conflict-rejecting reducer, three fixed nodes and guarded report construction. |
| `backend/app/modules/investigation/service.py` | Capture/release/run/recheck/publish transactions, idempotency and fresh applicability checks. |
| `backend/app/modules/investigation/routes.py` | Authenticated POST/GET transport; existing session and CSRF enforcement. |
| `backend/app/modules/investigation/__init__.py` | Module boundary. No financial mutation tools. |
| `backend/app/db/models.py` | New `InvestigationRun` mapping only; existing invoice/ledger models retain their contracts. |
| `backend/alembic/versions/0006_investigation.py` | Additive table/index/constraints; downgrade removes only the new table. |
| `backend/app/main.py` | Private router registration and new migration readiness revision. Public branch returns before registration. |
| `backend/app/core/config.py`, `.env.example` | Separate `INVESTIGATION_MODE=mock`; live investigation modes are rejected. |
| `backend/requirements.txt` | LangGraph and resolved transitive pins; existing dependency pins preserved. |
| `backend/tests/test_investigation.py` | Graph, contract, authorization, stale-output, race, replay and financial immutability checks. |
| `backend/tests/test_postgres.py` | Existing migration round-trip assertion follows the new head. |
| `backend/app/qa.py` | Restores benchmark usability after the prior auth upgrade: real cookie login and CSRF replace obsolete Basic Auth. |
| `scripts/dev.py` | Forces offline model settings in tests instead of inheriting live `.env` values. |
| `scripts/run_investigation_demo.py` | Reproducible synthetic API example using a disposable schema and no financial writes. |
| `README.md`, `docs/architecture.md`, `docs/day-6-progress.md` | Current usage, implemented architecture, actual results and limits. |

## Follow one request

1. The existing auth dependency verifies the operator cookie and POST CSRF token.
2. `start_investigation` locks the invoice briefly. The expected revision must
   match; the invoice must be NEEDS_REVIEW with current extracted data and blockers.
3. `snapshot_invoice` selects only failed BLOCKER rules in the current revision
   and validation batch. It captures identifiers, hashes, currency and recorded
   amount evidence, not the uploaded file, credentials or full invoice payload.
4. An investigation row is committed before graph execution. No invoice column,
   validation record, supplier, approval, ledger entry or financial audit changes.
5. `build_graph` compiles snapshot -> investigation -> advisory-report nodes.
   Each node returns a partial state update; it does not mutate shared ORM objects.
6. The mock provider returns structured findings. The report node verifies exact
   allowed claims and evidence references against the snapshot before publishing.
7. A new short transaction refreshes and locks the invoice. If the revision,
   payload hash, validation batch, source hash or eligibility changed, output is
   STALE. Otherwise the advisory report is stored as COMPLETED.
8. GET rechecks applicability. A historical report remains stored but is not
   returned as current after an input change. GET does not rewrite audit records.

## Concepts to study

**Graph versus agent.** A graph is explicit control flow over state. Here there
are three fixed nodes and no autonomous planning. LangGraph does not itself make
this mock intelligent. The supervisor belongs to the next milestone.

**Typed state versus runtime validation.** `InvestigationState` is a TypedDict for
developer/tooling feedback. Pydantic validates runtime inputs/outputs. Strictness,
forbidden extra fields, revalidation and frozen nested tuples prevent accidental
coercion or mutation across the provider boundary. JSON naturally represents UUIDs
and tuples as strings/arrays; Pydantic's JSON validation restores their strict types.

**Dependency inversion.** `InvestigationProvider` describes the behavior needed
by the graph. The mock implements it without depending on Gemini extraction.
Future providers must satisfy these boundaries; do not enable live execution by
loosening the current guard or removing the mock-only configuration constraint.

**Reducers.** `merge_findings` merges by stable task ID, sorts deterministically,
accepts identical repeats and rejects conflicting results. Unbounded list appends
could duplicate claims on retries. This milestone uses sequential nodes; the
reducer is not evidence that parallel investigators have been implemented.

**Idempotency versus retries.** Reusing a request key returns the same run, even
if failed or still running. Changed input under that key returns 409. It does not
silently retry a model call. Use a new key for a deliberate new mock run. A crash
can leave RUNNING records; recovery is intentionally deferred to Day 12.

**Transactions and the identity map.** SQLAlchemy may retain an object in memory
when `expire_on_commit=False`. Another transaction can change the real invoice
while the graph runs. A later SELECT does not necessarily replace cached fields.
Study `locked_invoice(...populate_existing=True)`: locking and refreshing solve
different problems. The race test proved this mattered.

**Grounding is limited.** A citation to an existing validation row supports the
statement that validation recorded a mismatch. It does not establish whether the
source document or extraction was wrong, prove authenticity or authorize a change.
The output therefore asks for evidence instead of changing a total.

## Safe modifications and an exercise

Start with `expected_finding`, then `build_graph`, then the transaction boundaries
in `start_investigation`. Finally read the race and unchanged-financial-state tests.

Exercise: add a small pure node before report construction that records a fixed
policy-version marker in typed state. Add an assertion that it runs without
changing findings or financial data. Do not add financial tools, change allowed
actions or introduce another blocker investigation until Day 7 is authorized.

Changing wording requires updating the mock's deterministic expected output and
relevant assertions. Supporting another exception is a semantic feature, not a
styling change. Keep the provider free of database sessions and arbitrary tools.

## Commands

From repository root:

```powershell
.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
.venv/Scripts/python.exe -m pip check
.venv/Scripts/python.exe scripts/dev.py test --postgres
.venv/Scripts/python.exe scripts/run_investigation_demo.py
```

Tests use random isolated PostgreSQL schemas. They never drop the application
schema. The demonstration removes its schema after writing a clearly synthetic
report. No investigation key, model access or external tracing account is needed.

Frontend regression commands, from `frontend/`:

```powershell
npm.cmd run typecheck
npm.cmd run test:e2e
npm.cmd run test:e2e -- --config playwright.public.config.ts
```

The progress report records what actually ran, including failures and fixes.

Official references consulted: [LangGraph Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api),
[StateGraph reference](https://reference.langchain.com/python/langgraph/graph/state/StateGraph),
[state and reducers](https://docs.langchain.com/oss/python/langgraph/graph-api-state).
