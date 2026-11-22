# Day 8: parallel investigators and supporting evidence

The graph now follows snapshot → supervisor/read capture → financial, supplier and
document branches → explicit join → advisory report. It remains a scripted offline
mock, not live autonomous reasoning. Financial checks still belong to the existing
deterministic validation and posting transactions.

## Why the graph changed

Day 7 dispatched one role at a time. Day 8 fans out to three fixed nodes in the same
LangGraph superstep. Each node selects only its validated mandatory tasks; a role
with no tasks returns an empty finding map. An AND edge from all three nodes waits
for completion before reporting. Never infer completion from the fastest branch.

The shared findings channel uses a reducer. A reducer defines how concurrent partial
updates combine: keys are stable task IDs, keys are sorted, identical repeats are
idempotent, and conflicting values raise an error. Arrival order cannot decide which
financial claim wins. The maximum is 64 blocker tasks plus one document inventory task.

Read `graph.py:merge_findings`, `build_graph` and the final list-valued `add_edge`.
The [official LangGraph control-flow documentation](https://docs.langchain.com/oss/python/langgraph/graph-api-control-flow)
describes parallel supersteps and AND joins. Installed 1.2.22 signatures were also inspected.

## Avoiding concurrency bugs

SQLAlchemy Sessions are not shared between workers. `service.py` captures bounded
lookups and document versions in a short transaction. `supervise` invokes each
allowlisted tool once, then branches read frozen Pydantic values. Workers return
only findings; they never race to update a shared mutable tool cache. The scripted
provider is stateless. A future live provider must be safe for concurrent calls.

The overlap test uses a three-party barrier. A sequential implementation cannot
pass it. It also measures actual start/end intervals and checks their intersection.
This proves overlap in the test, not a production latency promise.

## Supporting evidence is a separate concern

`InvestigationDocument` and migration `0007_investigation_documents` add a separate
append-only table, indexed by invoice and normalized supplier. Its source/version
primary key retains old content; PostgreSQL rejects UPDATE and DELETE. Corrections
are new versions. These protections do not constrain a database administrator.

`documents.py` selects the latest version per source within BOTH invoice ID and
supplier identity, caps the captured sources at 12, and signals truncation. Pydantic
checks identity, duplicate source IDs and content integrity before graph execution.
The content digest is SHA-256 of canonical JSON `{"text": content}`, using the
existing `payload_hash` helper; it is not the hash of an original PDF file.

The sixth tool returns an inventory of PO, receipt and email kinds. The document
finding always abstains from reconciliation: text presence is not evidence of
authenticity, matching amounts, supplier approval or permission to post. Even when
all kinds are present, its status is `INSUFFICIENT`. Conflicting amounts and injected
instructions are preserved in source storage, not obeyed or repeated as conclusions.

No document ingestion endpoint or live Gmail evidence import was added. The small
JSON corpus is explicitly loaded only by the isolated demo. Production invoices
without linked evidence receive an honest missing-evidence result. Exact scoped
capture is not hybrid retrieval; search/ranking and resolvable evidence links are Day 9.

## Freshness and compatibility

New run snapshots include the bounded document read set. Finalization and every GET
compare it with current captured evidence. Appending a source or a newer visible
version makes the old report stale while retaining its stored report. Old Day 6–7
snapshots without `documents` keep their original semantics and remain readable.
Changes outside a truncated read set cannot be discovered by comparing that read set;
the report states the truncation and never treats an incomplete inventory as complete.

## Files to study and modify independently

- `schemas.py`: immutable evidence contracts, size limits and scope/integrity checks.
- `documents.py`: exact SQL capture; change query limits and contracts together.
- `routing.py`: mandatory document inventory task; provider cannot omit it.
- `tools.py`: inventory only, no database/session/network capability.
- `providers.py`: deterministic mock document finding; no monetary inference.
- `graph.py`: fan-out, conflict-rejecting reducer and join.
- `service.py`: snapshot/finalization/read applicability boundaries.
- `db/models.py` and migration `0007_investigation_documents.py`: evidence persistence.
- `fixtures/investigation/day-8-corpus.json`: four synthetic supporting texts.
- `scripts/run_parallel_demo.py`: missing/populated evidence and stale-report demo.
- `tests/test_investigation_parallel.py`: overlap, scope, injection, immutability and freshness.
- `tests/test_investigation_routing.py`: order assumptions now test join boundaries.
- `app/main.py`, `tests/test_postgres.py`: expected migration head.

## Run it

From the repository root, with local PostgreSQL running:

```powershell
.venv/Scripts/python.exe scripts/dev.py test --postgres
.venv/Scripts/python.exe scripts/run_parallel_demo.py
.venv/Scripts/python.exe -m pytest backend/tests/test_investigation_parallel.py -k overlap -s -q
```

The demo uses cookie authentication and a disposable random database schema. It
does not seed evidence into your real invoice database, call Gemini or send Slack.
Its report output goes to ignored `storage/day-8-synthetic-reports.json`.

Exercise: reverse the order of finding updates and explain why the report stays
identical. Then propose a contradictory update for the same task ID and verify that
the reducer fails instead of choosing the last writer. Finally append a new source
version and trace why GET hides the older report without deleting its stored content.
