# Day 13 — Live Gemini investigation through MCP

19 November 2026. A live investigation now passed deterministic validation and
semantic review without repairs. See [the latest verification note](investigation-verification-2026-11-19.md)
for metrics, grounding fixes and remaining limits. Historical attempts below are
retained; the stricter synthetic pair and full regression are not marked passed.

## Implementation

The new versioned live path supplements the original scripted graph. The worker
still owns the queue, lease, fence, frozen invoice projection and final freshness
check. Gemini selects tool calls; the host sends authorized empty-argument calls
through an official MCP client to the existing stdio adapter. The adapter uses
the same read projections as offline investigation. No model has a database
connection, financial mutation tool or posting authority.

`gemini_provider.py` performs one `generate_content` request per public method.
SDK automatic function execution and SDK retries are disabled. The host owns
request retries and cumulative limits. Gemini timeout values are converted from
seconds to SDK milliseconds. Connection, read, write and pool timeout failures
have separate sanitized codes. Operational logs contain no model text, source
contents, credentials or hidden reasoning.

`live_schemas.py` defines validated local protocol history, function call IDs,
opaque base64 thought signatures, usage counters, findings, exact assertions,
drafts and critic verdicts. Optional thought text is excluded. No SDK model or
pickle is saved in durable checkpoints.

`live_policy.py` checks mandatory tool coverage, actually delivered reference
membership, frozen source identity/version/hash/excerpt and JSON Pointer fact
values. Monetary assertions preserve exact decimal strings and currency. The
qualitative prose output format excludes digits; factual values belong in
typed assertions. This format rule does not prove arbitrary prose or detect
spelled-out false claims. Semantic support remains a critic and human-review
responsibility. A model critic cannot override deterministic rejection.

## Verification recorded so far

- Provider/grounding unit tests: **24 passed**, 6.47 seconds, exit 0.
- Tests include installed SDK serialization with HTTPX MockTransport; no network
  or paid request was used. This checks local SDK compatibility, not live account
  or model capability.
- Tests cover signature/call-ID checkpoint round trip, omitted hidden thought
  text, single SDK attempt, timeout units and all four HTTPX timeout categories,
  structured output, finish reasons, malformed/empty output, precise monetary
  assertions, fabricated references, field paths and currency semantics.
- Ruff passed for the provider, contracts, policy and provider tests.
- First paired live smoke: **FAILED**, both variants. Each reached the real
  configured Gemini model (716 reported tokens) and three actual MCP tool results,
  then stopped with a safe worker failure before the second model turn. No
  financial records changed and the disposable schema was removed. This is not a
  successful investigation. The sanitized result is preserved separately as
  `storage/day-13-live-smoke-attempt-1.json`; further paid calls wait for a known fix.
- Initial live integration test batch: **5 passed, 1 failed**, 73.86 seconds. An
  isolated rerun identified a real abstention-path bug: the live graph supplied a
  critic code outside the strict `ResolutionReview` allowlist. It has been changed
  to the existing `CRITIC_REJECTED` code. The unchanged strict abstention assertion
  and new public-mode live-configuration denial both passed in an isolated rerun:
  **2 passed**, 58.22 seconds, exit 0.
- Full backend/browser regression and container activation: results pending.
  A full current-backend run was intentionally stopped before its summary while
  Docker builds, browser tests and shared tool-contract edits overlapped. Its
  partial E/F markers are not a completed regression result. A fresh quiet-window
  run is required; prior passing counts do not substitute for it.

An initial unit run reported 10 passes and 8 failures while the shared
`ToolResult.data` contract was still being implemented in parallel. After that
contract landed, all 18 original tests passed. Three additional tests brought
21; three source-integrity cases brought the current total to 24. No failure was
hidden or changed into a skip.

## Bounded paid smoke

`scripts/run_live_investigation_smoke.py --run-paid-synthetic` creates an isolated
`ied_qa_<uuid>` PostgreSQL schema and a synthetic operator session. Extraction
uses the bundled mock fixture; only investigation calls Gemini. It uses the
configured model/key without printing either the key or any prompts.

The pair holds invoice values and initial blockers constant. A versioned PO
record changes from amendment-present to amendment-absent, with a fresh random
record marker absent from the initial prompt. The script performs one worker
attempt per variant, records failures, and never reruns a pair to obtain a
preferred stochastic answer. Run-level bounded HTTP retries are separate.

Checks require a live accepted report, multiple tools and model turns, actual
versioned source citation and exact withheld-source assertion, changed conclusion
or uncertainty, and byte-equivalent financial table contents before/after. The
script drops only its own verified random schema and confirms its removal.

Metrics go to `storage/day-13-live-smoke.json`. Full controlled synthetic reports
go separately to `storage/day-13-live-synthetic-reports.json` for human semantic
review. Neither contains protocol history or hidden reasoning. A changed answer
alone is not proof of correct causal reasoning or a quality benchmark.

## Limitations

- One live investigator session initially; the mock graph retains parallel roles.
- The same model generates and critiques; correlated mistakes remain possible.
- Citations establish provenance, not original-document authenticity or truth.
- Read tools expose bounded frozen lexical retrieval, not general semantic RAG
  or model-selected global search.
- A crashed ambiguous request may be billed; conservative reservations persist.
  Exactly-once model calls and exact monetary billing caps are not promised.
- No conclusion here authorizes payment, supplier approval or ledger posting.

See [the implementation learning guide](learning-day-13.md) and
[approved Day 13 integration plan](phase-2/DAY_13_LIVE_INVESTIGATION_PLAN.md).

## Follow-up diagnosis and container update

The second paid smoke failed before investigation with a database OperationalError.
The third preserved attempt exposed `MODEL_TOOL_NOT_ALLOWED` after three actual
MCP results; one variant also timed out under severe concurrent build/test load.
Host authorization correctly rejected the model request. Gemini now uses
`VALIDATED` function calling, authorized names and explicit empty-argument schemas;
three offline SDK-wire/host-denial regressions passed.

The fourth paired smoke completed four MCP tools and two model turns per variant,
but the structured writer request was rejected. A separate static-schema request
confirmed HTTP 400: the legacy SDK `response_schema` serialization sends unsupported
`additional_properties`. The provider now follows the existing extractor's
`response_json_schema` path, retaining strict local Pydantic validation. Final paid
verification after this fix is still pending; these attempts are not successful
investigations and no financial records changed.

The pinned SDK's HTTPX MockTransport regression verifies the outgoing
`generationConfig.responseJsonSchema` retains local shape, types, enums and
`additionalProperties: false`, while legacy `responseSchema` and the unsupported
`additional_properties` key are absent. Provider/tool-contract offline
verification after the first wire fix: **28 passed**, exit 0, 14.47 seconds.
The deterministic initial rule-evidence declaration and later dynamic tool
availability are also covered; this test does not claim a successful live call.

The fifth pair satisfied causal tool ordering: rule evidence was returned before
Gemini selected additional invoice/document/search tools. However, its writer
request exposed a second HTTP 400: the nested bounded schema exceeded Gemini's
constrained-decoding state limit. A static-only diagnostic reproduced that exact
error. The wire adapter now omits only `minItems`/`maxItems`; all authoritative
Pydantic array limits remain unchanged and over-limit output is rejected locally.
This follows [Google's schema-complexity guidance](https://aistudio.google.com/docs/structured-output).

One bounded static compatibility request after that fix **passed**: configured
Gemini accepted the schema, finished with `STOP`, used 252 reported tokens
(19 input, 233 output) and took 2.733 seconds. It contained no invoice data. This
proves provider-schema compatibility, not successful evidence investigation.
Final genuine paired investigation and the fresh frozen full regression remain
pending. Three added regressions check local finding/assertion/reference limits
still reject oversized arrays despite the simplified wire schema.

The completed host regression returned **392 passed, 4 failed, 5 setup errors**,
exit 1, 943 seconds. The five setup traces explicitly reported PostgreSQL had not
yet reached consistent recovery; a subsequent isolated authentication test passed.
Two actionable failures were fixed: successful worker events no longer include
an unnecessary `error_site: null`, preserving their existing shape, and the
redaction unit test restores its logger after Alembic's in-process logging setup.
The other failures were an early PO MCP-delivery interruption and an explicitly
logged rich-document MCP timeout. All four failed cases then passed together:
**4 passed**, exit 0, 31.91 seconds, with no increased timeout or weakened
evidence-consumption, redaction or financial-invariance assertion. The final full
suite will run against the rebuilt Linux backend image; the host failure is
preserved and is not being relabeled as a passing full regression.

The frontend, backend and worker were rebuilt and started on 19 November 2026.
PostgreSQL and n8n were preserved. A custom-format database backup was made before
migration `0010` and its archive table of contents was readable. The backend is
healthy; final code refresh and verification results will be recorded below.

### Evidence-reference follow-up, 19 November

See [the evidence-reference fix report](evidence-reference-fix.md) for the explicit
root contract, strict conditional normalization and bounded repair changes. The
latest paid synthetic pair had zero reference rejections; one report passed the
deterministic gate and semantic critic within six steps. The broader pair smoke
still failed canonical source-citation checks, and manual review found a prose
overstatement missed by the critic. Day 13 live semantic acceptance remains open;
do not treat the pointer fix as a complete milestone acceptance. No limits were
increased and no financial writes were authorized by the investigation.
