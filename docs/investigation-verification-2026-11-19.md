# Live investigation verification and grounding fixes

19 November 2026. Local preservation checkpoint on `feature/phase-2-days-13-14`.
This note records existing execution results; preparing the commit did not run
another investigation, change application logic or rebuild containers.

## Latest accepted live execution

Configured model: `gemini-3.1-flash-lite`. The run started at 18:01:59 PKT and
finished at 18:03:25 PKT. Only aggregate metrics and generic assertion paths are
recorded here. Private invoice, supplier, source and execution identifiers,
document contents, credentials and raw model responses are intentionally omitted.

| Metric | Latest successful execution | Immediately preceding failed execution |
| --- | --- | --- |
| Final status | COMPLETED; report accepted | FAILED; INVESTIGATION_MODEL_BUDGET |
| Deterministic validation | Passed; zero errors | Not reached |
| Semantic critic | Accepted; critic call completed | Not reached |
| Logical model calls | 6: four investigation turns, writer, critic | 3 attempted |
| Generation HTTP attempts | 8: six succeeded, two failed | 6: two succeeded, four failed |
| Report repairs | 0; first draft accepted | 0; no draft produced |
| Successful MCP calls | 4 | 2 |
| Reported input tokens | 8,624 | 2,285 |
| Reported output tokens | 794 | 24 |
| Total reported tokens | 9,418 | 2,309 |
| Requests with unknown usage | 2 | 4 |
| Budget charge including unknown-usage reservations | 20,265 | 22,641 |
| Total elapsed time including queueing | 85.76 seconds | 106.73 seconds |
| Elapsed time after worker claim | 84.25 seconds | 105.93 seconds |

Budget charges include conservative reservations for requests without usage
metadata. They are not confirmed provider billing. The successful execution
recovered from two HTTP 503 server errors using the existing bounded retry policy.
The earlier failures predate detailed HTTP diagnostics; their exact HTTP statuses
cannot be inferred retrospectively.

The successful execution called `get_rule_results`, `get_supplier_policy`,
`get_supporting_documents` and `search_evidence` through the read-only MCP client.
The preceding failed execution reached only the first two tools.

| Evidence source | Assertion path | Asserted value | Captured value |
| --- | --- | --- | --- |
| Supplier policy | `/policy_found` | `false` | `false` |
| Supporting documents | `/has_sources` | `false` | `false` |

Both assertions matched exactly, including boolean type. These establish absence
in the scoped registry lookup and captured document result; they do not establish
supplier illegitimacy, global document absence, invoice approval or payment authority.
The stored accepted review and completed critic call establish the accepted
semantic verdict; a separate verbatim accepted-critic explanation is not retained.

## Semantic grounding and repair changes preserved

- Tool data includes backend-derived `policy_found` and `has_sources` booleans.
  A missing supplier policy remains available as `/policy = null`. The model must
  not use supplier identity as proof of policy absence, or `truncated = false`
  as proof that a document collection is empty.
- JSON pointers are relative to the cited data object, not its response envelope.
  `/data` normalization is narrowly conditional on an unambiguous existing target.
  Unknown fields, IDs, wrong values/currencies and malformed pointers still fail.
- Repair feedback identifies the rejected finding index and offers relevant
  delivered absence evidence. A supported finding needs assertions; unsupported
  claims must remain insufficient rather than borrowing unrelated scalar fields.
- Repeated invalid repairs stop early. Terminal rejection details and bounded
  critic feedback are retained in protected checkpoints, including exhaustion.
- Rejected reports with termination codes become FAILED and are not applicable
  reports. Legacy completed records with those codes are presented as failed;
  historical records are not rewritten. Accepted reports about missing evidence
  remain distinct from technical failure.
- Provider diagnostics distinguish rate limiting, server errors, request
  rejection, network subtypes and connection/read/write/pool timeouts. Only safe
  status, allowlisted subtype, retryability and numeric retry hints are retained.
  Retry scheduling is observable; provider bodies, URLs, headers, keys and invoice
  contents are not operational diagnostics. Numeric retry hints are informational;
  this diagnostic change did not alter retry scheduling.

The eight-step, twelve-request, twelve-tool, two-repair, 24,000-token and
180-second defaults were not increased. Financial validation, approvals, supplier
authorization and ledger posting remain deterministic and human-authorized.

## Targeted verification already completed

- Grounding/reference/tool-contract checks: 26 passed.
- Grounding worker/MCP and failed-report API classification: two targeted cases
  passed. An initial authentication-helper mistake in the test was fixed and
  that failed case was rerun successfully.
- Provider/transport diagnostics and tool-contract checks: 44 passed.
- Persisted diagnostics/retry and durable budget regression: two passed, with six
  existing Starlette test-client cookie deprecation warnings.
- The changed diagnostic files passed Ruff lint/format checks; whitespace checks
  passed. Backend and worker were subsequently updated; backend health passed.

These focused batches overlap and must not be added into a unique-test total.
No new test suite or live execution was run for the preservation commit.

## Remaining limits

One accepted live investigation proves this execution path, not general semantic
accuracy. The earlier synthetic counterfactual pair did not meet its stricter
versioned-source citation checks and had a critic-missed prose overstatement;
those failures remain recorded in [the reference report](evidence-reference-fix.md).
This successful missing-document case does not exercise versioned document
citations or close that separate evaluation gap. The full Linux regression remains
unexecuted, and the historical host full-suite failure is not reclassified as a pass.
No next milestone or remote publication is authorized by this checkpoint.
