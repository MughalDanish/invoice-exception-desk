# Gemini evidence references: root contract and bounded repair

Latest follow-up: [semantic grounding fixes and accepted live results](investigation-verification-2026-11-19.md).
The historical failures below are retained and are not relabeled as passes.

19 November 2026. This is a small extension of the existing live provider; no new
reference storage, database migration, financial rule or write tool is introduced.
The eight-step investigation limit and existing token/tool/time limits stay unchanged.

## Contract and trade-off

Evidence IDs already come from the backend: scoped lookup digests and immutable
source/version/content hashes. Gemini must copy them from delivered evidence.
A field path is RFC 6901 relative to the chosen evidence object. For a tool result
this object is `result.data`; for a versioned source it is the source itself.
Valid examples: `/supplier_key`, `/rules/0/expected_amount`, source `/text`.
Invalid envelope examples: `/data/supplier_key`, `/data/rules/0/expected_amount`.
Escaped field names use `~0` for tilde and `~1` for slash. Array indexes are canonical
zero-based integers. Negative, leading-zero, nonexistent and malformed paths fail.
Only exact scalar values can be asserted; arrays/objects must not be stringified
or replaced with fabricated nulls. Missing support remains insufficient evidence.

A single `/data` prefix is removed only if the literal original pointer fails and
the stripped pointer resolves in the same backend-delivered evidence object.
Unknown IDs and nonexistent paths are not repaired. If both pointers resolve,
the original literal path is retained, with no guess based on the proposed value.
Exact type/value, Decimal currency, source/version/hash, mandatory tool coverage
and all other deterministic gates still apply after normalization.

A new field-level fact-ID catalogue could further reduce pointer mistakes, but
would introduce another persisted mapping and versioned output contract. Existing
backend evidence IDs plus explicit roots, bounded valid-leaf guidance and strict
normalization solve this observed mismatch with less complexity. Reconsider fact
IDs only if measured pointer failures persist after this fix.

## Repair and observability

Repair guidance privately includes the rejected ID/path, reason and bounded valid
leaf paths (plus delivered IDs for unknown references), without adding invoice
values to telemetry. Report repairs return directly to the structured writer;
only missing mandatory tool coverage returns to tool selection. Actual bounded
critic reasons accompany private repair feedback. Once mandatory tools have been
delivered, the host routes directly to drafting instead of asking the model for
a redundant stop turn. Independent follow-up tools may be batched after the rule
anchor. This saves calls, without increasing any limit. The trade-off is bounded
evidence collection: unresolved questions remain explicit rather than triggering
open-ended tool exploration.
Fingerprints detect repeated identical rejected assertions; they stop early with
safe abstention. Distinct failures retain the existing maximum two repairs.
Rejected claims/assertions are never published as accepted findings.

Specific safe termination codes distinguish invalid repeated references,
identical non-reference repairs and exhausted repair allowance. The optional
report termination code is also exposed through the existing run error code.
Successful accepted reports have no termination code. Existing safe abstentions
retain their completed/advisory semantics, with an explicit stop reason.
Transport failures retain provider-specific codes and bounded retries. Actual
model-budget failures remain separate and record whether model steps, HTTP
attempts or cumulative tokens caused the stop. Operational events contain only
codes, counts and resource names, not rejected paths, evidence text or credentials.
Authorization/deadline errors retain their specific safe codes instead of becoming
a generic worker error.

## Important files

- `backend/app/modules/investigation/gemini_provider.py`: prompt contract/examples.
- `live_policy.py`: strict pointer resolution, conditional normalization, bounded
  scalar path catalogue and private targeted feedback.
- `live_graph.py`: full revalidation, direct writer repair, fingerprints and stop reasons.
- `budgets.py`: resource-specific budget telemetry without increasing limits.
- `schemas.py`, `worker.py`: additive report/run termination metadata.
- `service.py`: new runs record prompt version `live-v2-evidence-root`.
- `backend/tests/test_investigation_references.py`: root, escaping/index, ambiguity,
  strict monetary validation, feedback and repair-loop regressions.
- `backend/tests/test_investigation_live.py`: durable budget telemetry regression.

## Verification

Focused provider/reference/tool-contract final batch: **53 passed**, exit zero, 14.76s.
This includes empty collections and direct critic repair. An earlier PostgreSQL
live/durable/recovery batch passed 21 tests before the routing refinement; the
durable token-budget telemetry regression separately passed. The host rerun after
routing changes terminated abnormally (exit -1) without a final pytest summary;
it is not counted as a passing run. The final local PostgreSQL live-worker,
document checkpoint and recovery batch then passed **12 tests**, exit zero,
182.95s, with 34 existing Starlette cookie deprecation warnings. This includes
logout authorization, denied write/cross-invoice tools, safe repair exhaustion,
deadline/auth error classification, durable token limits and recovery.
Ruff lint/format and `git diff --check` passed. A full Linux regression remains
unexecuted; these are focused checks, not a full-suite passing claim.

Paid synthetic attempts are retained rather than overwritten as successes:

- Attempt 1: both cases failed; one exhausted eight steps after critic rejection,
  the other lost authorization. Root-corrected drafts reached the critic.
- Attempt 2: both cases failed; one exhausted the cumulative token reservation
  during repair at seven steps; the other hit the existing run deadline. This
  motivated independent tool batching and explicit document-linkage uncertainties.
- Attempt 3: **zero reference rejections in both cases**. Variant two completed
  in six logical steps / six HTTP requests, 39.875s, 11,610 reported tokens,
  with both deterministic validation and semantic critic acceptance. Variant one
  had a semantic rejection and a transport retry with unknown usage; its token
  reservation stopped the next draft (six logical steps / seven HTTP attempts).
  The pair smoke exited 1: its stronger versioned-source-ID assertion checks did
  not pass. The accepted report used a valid tool-root `/sources/0/text` assertion
  rather than the required canonical versioned source ID. This is not a pointer
  failure, and the acceptance check has not been relaxed.
- The accepted synthetic report was manually inspected. Its assertions match
  delivered evidence, but its prose overstates the rule's expected amount as a
  purchase-order amount. The critic did not catch that semantic overstatement.
  Exact pointers cannot prove arbitrary prose entailment; do not treat this test
  as proof of full live-investigation semantic reliability. Financial authorization
  remains separate and deterministic. Improving semantic citation/entailment is
  still open; this change does not certify the broader Day 13 smoke as passing.
- No model/HTTP/token/tool/deadline limits
  were raised, and no real financial records were changed by these tests.

Backend image build succeeded with the dependency-install layer cached. Running
the Docker regression command was denied by the permission control; it was not
executed. Backend and investigation-worker recreation was separately requested
under the user's existing authorization; final health is recorded below.

Commands from the repository/backend environments:

```powershell
# From backend
..\.venv\Scripts\python.exe -m pytest tests/test_investigation_references.py tests/test_investigation_gemini.py tests/test_investigation_tool_contract.py -q
# From repository root; isolated synthetic PostgreSQL schemas and offline model
.venv/Scripts/python.exe scripts/dev.py test --postgres
# Explicitly paid, isolated synthetic invoices, real Gemini and actual stdio MCP
.venv/Scripts/python.exe scripts/run_live_investigation_smoke.py --run-paid-synthetic
```

No claim of general semantic correctness or prompt-injection immunity follows
from one synthetic pair. Human approval, deterministic validation and posting
remain separate from investigation recommendations.
