# Understanding live financial investigation

Day 13 introduces a real model/tool conversation while keeping financial
authority in ordinary backend code. Start with this distinction: Gemini chooses
what evidence to request and proposes a resolution; Python decides what it may
read, whether its statements are grounded and whether its advisory result is
still applicable. Existing financial workflows remain separate.

## Follow one investigation

1. An authenticated operator enqueues a reviewable invoice revision. The server
   freezes its evidence projection and records the requesting user/session.
2. The PostgreSQL worker claims a lease and fence. It chooses the versioned live
   graph for a Gemini run and retains the old graph for scripted offline runs.
3. `initial_history` supplies blocker codes and mandatory objectives. It does
   not include the supporting document text or expected answer.
4. `GeminiInvestigationProvider.step` sends authorized function declarations.
   The first turn exposes only the mandatory rule-evidence tool as a deterministic
   foundation. After that result, all authorized tools are exposed and Gemini
   selects the additional evidence. The initial anchor is not claimed as an
   AI decision. A function call is a model request, not executed Python code.
5. The graph validates the requested name/arguments and budget, then the MCP
   client sends `tools/call` over stdin/stdout to an owned local subprocess.
6. The adapter verifies identity, session, run scope and current applicability,
   then returns bounded read-only evidence from the frozen projection.
7. `function_result_content` preserves the model's call ID and returns that
   result to Gemini. A later request can depend on what the model just learned.
8. A separate tools-disabled request creates a strict `LiveDraft`. Code validates
   facts and references; a bounded Gemini critic reviews semantic support.
9. The worker publishes advisory output only while it still owns the lease/fence
   and the underlying financial/evidence revision remains current.

## Files to study

| File | Responsibility |
| --- | --- |
| `backend/app/modules/investigation/gemini_provider.py` | Single-request SDK boundary, prompt, history translation, structured writer/critic, count-token preflight |
| `backend/app/modules/investigation/live_schemas.py` | Closed local protocol and live-report contracts |
| `backend/app/modules/investigation/live_policy.py` | JSON Pointer assertions, delivered-reference manifest, source/currency/precision checks |
| `backend/app/modules/investigation/live_graph.py` | Checkpointed model → tool → draft → review → publish orchestration |
| `backend/app/modules/investigation/budgets.py` | Durable reservations, cumulative usage, time/call/tool limits and bounded host retries |
| `backend/app/modules/investigation/worker.py` | Existing durable job execution and final publication boundaries |
| `backend/app/modules/investigation/mcp_adapter.py` | MCP protocol and read-only authorization boundary |
| `backend/app/modules/investigation/mcp_client.py` | Official MCP client lifecycle, strict tool discovery, request deadlines and owned subprocess cleanup |
| `backend/app/modules/investigation/delegation.py` | Short-lived run-scoped capabilities and active-session/fence/freshness verification |
| `backend/app/modules/investigation/mcp_stdio.py` | In-image child entry point with sanitized environment and no dotenv/key loading |
| `backend/tests/test_investigation_gemini.py` | Fast offline protocol and grounding tests |
| `backend/tests/test_investigation_live.py` | Fake model with real PostgreSQL and MCP; authorization, evidence flow, budgets and safe failure |
| `backend/tests/test_investigation_injection.py` | Host containment after deliberately hostile source instructions cross actual MCP |
| `fixtures/investigation/prompt-injection-cases.json` | Explicit synthetic PO/email attacks: posting, scope escape and external exfiltration |
| `scripts/run_live_investigation_smoke.py` | Disposable, bounded paid synthetic counterfactual pair |

The client and server are protocol adapters around the same domain tools. Avoid
putting a second financial rule implementation in either adapter. The capability
is a delegated read permission, not an ordinary login token; it is never shown
to Gemini or accepted by normal browser authentication endpoints.

## Why separate the provider and graph?

The provider translates one request/response and performs no tool execution or
database reads. The graph owns the conversation. This keeps network retries from
silently multiplying an SDK tool loop, makes each external boundary checkpointable
and allows fake model responses in tests without replacing the real MCP boundary.
Changing the prompt should not change authorization or financial policy.

The writer/critic use `response_json_schema`, matching the extraction adapter.
The older `response_schema` wire format rejected Pydantic's extra-field policy
as an unknown `additional_properties` property. Changing the wire format does
not loosen `LiveDraft.model_validate_json`: extra fields, invalid types, bounds,
amount precision and evidence checks still apply after the response arrives.
Nested finite array bounds also exceeded Gemini's grammar-state budget. The
wire-only adapter omits `minItems`/`maxItems`, while local Pydantic rejects too
many findings, assertions or references. Output-token and run budgets remain
enforced. Separate tests exercise both the serialized wire shape and rejection
of oversized local outputs, so API compatibility cannot silently weaken policy.

## Why local protocol DTOs?

SDK objects are convenient at the API boundary but fragile storage contracts.
`ProtocolContent` and `ProtocolPart` retain the bounded fields needed to resume:
role, visible content, function requests/results and opaque signatures. Signatures
are returned to Gemini unchanged, not decoded as thoughts. Optional internal
thought text is deliberately removed and is never a product/debugging feature.

## How assertions work

A finding can reference the exact tool result and assert:

```json
{
  "evidence_id": "returned-tool-evidence-id",
  "field_path": "/rules/0/expected_amount",
  "value": "2300.0000",
  "currency": "USD"
}
```

The value must equal the delivered string, including precision. `2300` is not
accepted as a replacement for `2300.0000`. A currency must match the scoped fact.
Source citations also bind an immutable source ID, version, hash and exact excerpt.
The code does not infer new amounts, repair arithmetic or decide authenticity.
`render_assertion` displays validated facts without a binary floating-point step.

This is stronger than checking that a citation exists, but it cannot prove the
semantic meaning of every sentence. A critic can catch contradictions and unsafe
certainty, but it is probabilistic. Human review remains an explicit product rule.

## Budgets, reservations and recovery

A model request may complete remotely just before the worker dies. Repeating it
can cost money. Record a conservative reservation before network I/O and reconcile
documented usage afterward. Unknown usage keeps the reservation. The graph's
checkpoint and the financial-style call ledger serve different purposes: the
checkpoint resumes computation; the ledger prevents retries from resetting limits.

`estimate_input_tokens` uses the SDK count API on a conservative input superset,
including system/schema overhead and a margin. It does not claim exact billing.
The SDK itself performs one HTTP attempt. The host decides bounded retries for
transient failures and records all attempts. Read, write, connection and pool
timeouts are distinct failures; the SDK configuration uses milliseconds.

## Modify components independently

- Improve wording in `SYSTEM`, then run protocol/grounding tests and evaluate
  live output. Do not weaken a failing policy check to accommodate an invented fact.
- Add an assertion shape in `live_schemas.py` and its verification in
  `live_policy.py` together. Keep exact Decimal/currency semantics.
- Add a tool only through the shared tool implementation, allowlist, MCP schema
  validation and authorization tests. Do not give the model SQL, URLs or paths.
- Change budgets through bounded settings and test cumulative behavior across
  retries/resumes. Avoid resetting counters in a graph node.
- Keep all new financial mutations outside investigation. Recommendations cannot
  call approval/posting code, even after a positive critic verdict.

## Commands

```powershell
.venv/Scripts/python.exe -m pytest backend/tests/test_investigation_gemini.py -q
.venv/Scripts/python.exe scripts/dev.py test --postgres
```

The paid smoke is deliberately explicit:

```powershell
.venv/Scripts/python.exe scripts/run_live_investigation_smoke.py --run-paid-synthetic
```

It performs only the bounded synthetic pair; inspect all failures and both
synthetic reports. A successful pair is an integration proof, not an accuracy
percentage or a substitute for held-out evaluation in Day 15.

## Provider schema versus authoritative validation

Gemini's legacy schema transport rejected `additional_properties`, so the provider
uses JSON Schema through `response_json_schema`, matching invoice extraction.
Its grammar compiler also rejected nested finite array bounds. The adapter removes
only `minItems` and `maxItems` from the wire schema; strict local models retain
those bounds and reject excess or missing items. This is a useful boundary pattern:
translate a vendor's supported contract without changing the application's
invariants. Output-token and run budgets still bound generation.

The first model turn exposes only recorded rule evidence as a deterministic
anchor. Subsequent turns expose the complete authorized tool set. Gemini chooses
follow-up evidence after receiving the rules; the host does not pre-run every
investigation tool or supply an expected report. This policy trades unconstrained
first-turn exploration for a known financial starting point.

Study `0010_live_investigation.py`, `models.py`, `service.py`, `routes.py`,
`controls.py` and `queue.py` alongside the live graph: they explain how identity,
mode and budgets enter the job and how existing offline records remain compatible.
`test_investigation_live_recovery.py` kills a real live-mode host using a fake model
and actual MCP, then verifies persisted history and budgets across a fresh claim.
`test_investigation_live_migration.py` verifies reversible empty-history upgrades
and refuses destructive downgrade of live or budget history.
