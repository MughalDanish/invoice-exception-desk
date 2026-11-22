# Day 7: supervisor, mandatory routing and read-only tools

Implemented locally on 18 November 2026 (Asia/Karachi), on the existing Phase 2 branch
`feature/phase-2-day-6-foundation`, starting at clean Day 6 commit `a5195b4`.
The user's latest direction explicitly limits this work to Day 7. No Day 8
parallel execution, PO/receipt/email corpus or later milestone was implemented.

## Previous milestone verification

The complete Day 6 backend/PostgreSQL suite was rerun before source edits:
**238 passed**, no skips, exit 0, 131.05 seconds. Existing cookie deprecation
warnings remain. The Day 6 progress report, current graph/provider/service,
roadmap, agent specification, architecture, security requirements and learning
objectives were inspected. No earlier test count was assumed to be current.

## Implemented

- A strict provider planning contract and mock supervisor inside the real
  LangGraph workflow. Deterministic policy derives mandatory tasks from blocker
  codes; proposed plans may reorder those tasks but cannot omit or change them.
- Four mandatory routes:

  | Blocker | Role | Required evidence tools |
  |---|---|---|
  | TOTAL_MISMATCH | Financial | Current rules and invoice/source snapshot |
  | DUPLICATE_INVOICE | Financial | Current rules and exact duplicate candidates |
  | UNAPPROVED_VENDOR | Supplier | Current rules and supplier policy |
  | AMOUNT_OUTLIER | Supplier | Current rules, supplier policy and same-currency history |

- Conditional dispatch to sequential financial/supplier workers. Unknown blocker
  codes are represented by explicit unsupported tasks and insufficient findings;
  they are never silently skipped. No parallel-execution claim is made.
- Five allowlisted read-only tools with strict argument schemas and server-bound
  invoice/supplier scope. Unknown tools, write actions, arbitrary SQL, paths and
  scope spoofing are rejected. Tool results are cached by name, with a maximum of
  12 distinct calls; a combined four-class plan uses only five distinct reads.
- Bounded exact SQL projections captured before graph execution. Duplicate reads
  filter by supplier and invoice identity; history filters by supplier and
  currency. Each result collection is limited to 20 rows with explicit truncation.
  The provider and tools receive frozen data, never a DB Session or write handle.
- Findings cite captured evidence. No decimal is rounded, inferred or repaired.
  Original document contents remain unread; the source tool reports that limit
  explicitly. Historical samples are not treated as proof of fraud or legitimacy.
- Plans, used tool names and lookup digests are additive report fields. Old Day 6
  report JSON remains readable with defaults. Existing snapshots without lookup
  evidence retain their original applicability semantics.
- New snapshots include bounded lookup evidence. Supplier policy, candidate or
  history changes invalidate applicability, both before report publication and
  on subsequent GET. Existing invoice revision/hash/batch/source checks remain.
- All outputs remain advisory. The proposed action stays REQUEST_EVIDENCE;
  supplier approval, correction, invoice approval, posting and payments are absent
  from the tool allowlist and plan contract.

## Actual verification

| Command / check | Actual result |
|---|---|
| `python scripts/dev.py test --postgres` before changes | 238 passed, no skips, exit 0, 131.05 seconds. |
| Same complete suite after implementation | **268 passed**, no skips, exit 0, 165.56 seconds. Includes all original regressions and 30 new Day 7 cases. 358 existing-style per-request-cookie deprecation warnings. |
| `pytest ...test_investigation.py ...test_investigation_routing.py -m "not postgres" -q --tb=short` | **37 passed**, 19 PostgreSQL cases deselected, exit 0. This was repeated after adapting the negative-output test doubles to the per-task contract, preserving direct numeric/citation tampering checks. |
| `python scripts/run_routing_demo.py` | Exit 0: all four real API/mock-provider examples completed, invoice detail responses unchanged, zero ledger entries, all disposable schemas removed. Reports saved only to ignored synthetic storage. |
| Ruff lint and format checks on changed Python files | Passed after formatting. |
| `python -m pip check` | Exit 0; no broken requirements. No dependency was added or repinned. |
| Protected-path diff against `a5195b4` | Extraction, deterministic validation, approvals, ledger, n8n, original fixtures and frontend application source unchanged. |
| `npm.cmd run test:e2e` (private rerun, actual subprocess exit captured) | **2 passed**, exit 0, 2.8 minutes. Clean/correction/approval/posting, duplicate/supplier workflows, authentication and mobile controls. |
| `npm.cmd run test:e2e -- --config playwright.public.config.ts` | **3 passed**, exit 0, 1.3 minutes. Public immutability/mobile, untrusted evidence and loading/offline/error recovery. |
| Staged credential scan and `git diff --cached --check` | Passed; secrets, runtime data and diagnostic logs excluded. |

Neither browser suite uses the live application database. The initial private run
had 1 pass and 1 failure: the desktop test timed out while login was pending at its
15-second assertion deadline. Its trace showed an unfinished login request. The
unchanged suite then passed both cases; no timeout or auth setting was weakened.
The initial delay's cause was not proven, so the retry is not a cold-start latency
guarantee. The initial diagnostic wrapper also hit a Windows console encoding
error while printing Unicode; the replacement wrapper safely printed ASCII and
captured both actual test-process exit codes.

During development, an early unit-test collection hit an indentation error while
splitting a long string; it was fixed before the passing unit and full-suite runs.
The observed browser timing failure is retained here rather than omitted from the
passing final counts.

The safety cases cover all four routes, malformed/omitted/duplicate tasks, wrong
role/rule/tool, missing mandatory tools, unknown write actions, free-form arguments,
cross-invoice/supplier scope attacks, unknown blockers, missing currency evidence,
legacy report parsing, deduplication, bounded samples, policy changes during and
after execution, new duplicate candidates and unchanged financial records.

## Files and engineering decisions

New files:

- `backend/app/modules/investigation/routing.py`: mandatory routing and plan validation.
- `backend/app/modules/investigation/lookups.py`: exact, bounded source projections.
- `backend/app/modules/investigation/tools.py`: strict read-only capabilities.
- `backend/tests/test_investigation_routing.py`: 30 new safety/behavior cases.
- `scripts/run_routing_demo.py`: four reproducible synthetic examples.
- `docs/learning-day-7.md`, `docs/day-7-progress.md`.

Modified:

- Investigation `schemas.py`, `providers.py`, `graph.py`, `service.py`.
- `backend/tests/test_investigation.py`: retains Day 6 assertions while adapting
  internal provider doubles and the bounded recursion limit to the new graph.
- `README.md`, `docs/architecture.md`.

No migration is needed: source snapshots and report metadata fit existing JSONB
columns. Schema head remains `0006_investigation`. No original audit, validation,
approval, ledger or invoice record is rewritten. The test/demo helper may set a
synthetic supplier threshold only inside a disposable schema to create an outlier.

Captured projections make tool execution reproducible and remove DB capability
from provider code. The tradeoff is conservative staleness: the complete small
read set is compared even if a particular task did not use every captured field.
It is not a serializable proof that external evidence can never change. Financial
authorization still belongs to the existing fresh-validation posting transaction.

LangGraph remains 1.2.22. Official conditional-edge behavior was checked at
https://docs.langchain.com/oss/python/langgraph/graph-api-control-flow .
The mock supervisor deliberately uses ordinary code for mandatory routing; no
LLM is needed to decide which mandatory financial checks must run.

## Learning, limits and next milestone

Read [the Day 7 learning guide](learning-day-7.md). It traces the real request,
explains supervisor versus policy, conditional edges, strict tool schemas,
capability boundaries, deduplication and evidence freshness, and gives an exercise
that removes a mandatory history tool and verifies rejection before execution.

- Planning and findings are scripted mocks. Live AI reasoning quality, token/cost
  telemetry and retrieval metrics are **NOT RUN**. No paid model call or external
  trace was sent; configured Gemini extraction remains untouched.
- Execution is bounded synchronous local work. No worker, checkpoint recovery,
  cancellation, parallel fan-out, evidence document ingestion, RAG, critic or
  investigation frontend is introduced.
- Source references identify stored captured evidence; full evidence browsing and
  versioned document retrieval remain later milestones.
- Existing auth, public read-only behavior, financial APIs and workflows remain.
  Public mode registers no private investigation route and grants no model access.
- Running containers and private data were preserved. No new production image or
  frontend production build was run; no remote push or dev/main merge is performed.

Stop after the local milestone commit. Next, only after approval: **Day 8 parallel
investigators and a separately versioned synthetic PO/receipt/email corpus**.
