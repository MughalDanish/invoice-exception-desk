# R1 implementation guide: readable financial evidence

This guide explains the actual R1 code. Theme B is approved; R2, other redesign
packages and Phase 2 AI remain outside this implementation. The branch is
`feature/ui-r1-readable-evidence`, created from `3249bf1` while preserving the
existing untracked audit/concept directory. No remote push or deployment occurs.

## What changed and why

The invoice detail previously rendered audit details as expanded JSON, the original
extraction as a JSON-only disclosure, and rule codes as headings. R1 replaces those
presentations with an activity timeline, a structured original invoice summary and
failure-first validation evidence. Complete JSON remains available behind native
disclosures with copy and text-selection actions.

Small semantic distinctions matter: extraction is unverified source output; saved
corrections form a revision; validation records checks for a revision; human review
records a separate decision. None alone authorizes a payment. The new provenance
strip makes those facts visible without altering any action or backend policy.

Typography in new evidence views is consistently Segoe UI/Arial, 14px reading text,
12px metadata, 17px section headings. Deep teal and ink retain Theme B's identity.
The login story heading also uses the existing sans-serif family instead of Georgia,
following the explicit typography requirement. The small brand glyph is still a
logo treatment, not an editorial heading. No global component system, new font,
dashboard layout, dialog workflow, chart or AI panel was introduced.

## File map

Paths below are relative to the repository root. The prior audit/concept files
remain intact; the table identifies the R1 implementation files.

| File | Responsibility / reason |
|---|---|
| `frontend/src/lib/presentation.ts` | Pure money/date/label/event adapters, grouping and guidance. No requests, credentials, state mutation or financial authorization. |
| `frontend/src/components/evidence/technical-details.tsx` | Reusable collapsed JSON, safe token coloring, Copy and Select fallback, local feedback. |
| `frontend/src/components/evidence/evidence-value.tsx` | Recursive readable values/lists/objects, exact monetary strings and missing values. |
| `frontend/src/components/evidence/audit-timeline.tsx` | Ordered events, actual actor/time, icons, transitions, reasons, before/after and full event evidence. |
| `frontend/src/components/evidence/original-extraction.tsx` | Read-only supplier/identity/dates, lines, totals, source snippets, uncertainty and comparison with current saved data. |
| `frontend/src/components/evidence/validation-results.tsx` | Blocking failures first, warnings, expected/observed values, guidance and collapsed successful checks. |
| `frontend/src/components/evidence/record-context.tsx` | Original/current/corrected/validated/approved distinctions and review metadata. |
| `frontend/src/components/invoice-detail.tsx` | Composes the new views into existing detail; retains fetching, draft editing, action requests and gating. File integrity details become copyable; posted message no longer puts ledger UUID in primary prose. |
| `frontend/src/app/globals.css` | Scoped evidence styles, compact responsive rules and sans-serif login heading. Existing workspace/actions kept. |
| `frontend/package.json` | Adds `test:unit` using already-installed Playwright; no dependency/version change. |
| `frontend/playwright.unit.config.ts` | Runs pure TypeScript tests without browser, API or DB. |
| `frontend/unit-tests/presentation.spec.ts` | Exact decimal/currency semantics, labels, event types, malformed/unknown data, immutable inputs, real fixture coverage. |
| `frontend/tests/desk.spec.ts` | Existing isolated operator workflows plus original/current, approval provenance and exact correction evidence assertions. |
| `frontend/public-tests/public.spec.ts` | Existing anonymous readonly scenario plus collapse/copy behavior, missing extraction and inert untrusted unknown event. Screenshots now go to ignored R1 storage, preserving Day 5 artifacts. |
| `docs/ui-ux/tools/r1-capture.mjs` | Read-only before/after screenshots, four viewports, existing synthetic records, detail/audit equality checks. |
| `docs/ui-ux/R1_PROGRESS_REPORT.md` | Actual results, changed scope, screenshots, limitations and manual review. |
| `docs/ui-ux/R1_IMPLEMENTATION_GUIDE.md` | This guide. |

Backend, API types/transport, DB models/migrations, original fixtures, extraction
adapter, deterministic rule engine, approval service and ledger service are
unchanged. No additional runtime/test package was installed. Package lock inputs
do not require regeneration for an npm script addition.

## Component hierarchy

```text
DeskProvider                         Existing auth, public mode and workspace shell
  InvoiceDetail                      Existing fetch/draft/action orchestration
    Heading / Badge / Notice         Existing shared components
    RecordContext                    Saved revision and evidence provenance
      TechnicalDetails               Review/revision/ledger identity metadata
    Review invoice OR Audit history  Existing switching behavior
      Review invoice
        Source document              Existing protected blob preview/download
          TechnicalDetails           File identity and hash
        Invoice fields / actions     Existing form and financial workflow
        ValidationResults
          Check                      One existing rule outcome
            EvidenceValue            Expected/observed typed values
            TechnicalDetails         Complete original rule
          Successful checks          Native collapsed details
        OriginalExtraction
          EvidenceValue              Missing/source/diff values
          TechnicalDetails           Preserved original payload
      Audit history
        AuditTimeline
          EventIcon                  Small local SVG; no icon dependency
          EvidenceValue              Stored before/after values
          TechnicalDetails           Complete original event
```

This is composition: small components own one display concern while the existing
container owns I/O and draft state. The evidence components receive values as props;
none can call Save, Approve or Post. New future investigation layouts can reuse
EvidenceValue and TechnicalDetails without acquiring financial authority.

## Data flow: response to pixels

1. Existing `request()` fetches detail and audit endpoints using the existing token
   or anonymous public mode. No new endpoint or response field is required.
2. `InvoiceDetail.load()` stores the detail, clones current data into the existing
   editable draft and stores events. `extracted_data` remains distinct from the
   draft and current saved data.
3. Props flow into the read-only components. `auditView(event)` creates a separate
   **view model** with a title, description, icon, transitions, changes and notes.
   `validationGroups()` partitions a copy of rule references without modifying the
   response array. Original/current comparison compares values, not authorization.
4. Components format display-only strings and render React text. A technical
   disclosure receives the original event/rule/payload rather than the simplified
   view model, preserving fields an adapter does not yet understand.
5. Existing action callbacks still submit the original request shape, expected
   revision and decimal strings. Formatting is never fed back into the editor or
   request body. Commas exist only in read-only presentation.

The backend remains authoritative for current batch, revision/hash-bound approval
and fresh transactional posting. A displayed approval row means **a decision was
recorded**, not an independent client-side proof of eligibility. The unchanged
backend enforces payload binding on write.

## Study the presentation adapter

Start at [presentation.ts](../../frontend/src/lib/presentation.ts).

`decimal()` splits the original string at its decimal point and groups only the
integer substring. `financial()` prefixes an explicit currency code. For example:

```text
"9999999999999999.99", USD → USD 9,999,999,999,999,999.99
"1234", JPY              → JPY 1,234
"1234.00", JPY           → JPY 1,234.00 (preserved; validation decides acceptability)
"0.0000", USD            → USD 0.0000
null                     → Not provided (not zero)
```

No `Number`, `parseFloat`, `toFixed`, arithmetic or currency conversion is involved.
Supported formatting syntax is a signed plain decimal string. Scientific notation
or a malformed string is shown as supplied, not silently normalized. Unexpected
numeric values are not treated as precise money. No currency is invented for a
missing code. Original line quantities and unit prices retain their exact scales.

`ruleLabel()` explicitly maps failure-shaped codes to neutral names. A future
unknown rule gets “Additional validation check” and retains its full source code
under details. `outcome()` considers the actual passed flag first: a BLOCKER-severity
rule that passed is **Passed**, not a blocker. `validationGroups()` counts only
failed blockers and orders blocking failures before warnings/other failures, keeping
successful checks in their original sequence. These are presentation decisions;
they never change a persisted rule result.

`auditView()` switches on actual event types. State changes show actual recorded
from/to states, corrections use `details.diff`, notes remain exact text, and posting
uses the currency/total recorded in that event. It does not invent the actor:
AuditTimeline renders `event.actor` separately with a missing-data fallback.
An incomplete blocker summary does not become “zero blockers”. Unknown events
remain visible with generic wording and their complete technical payload.

Historical correction diffs do **not** borrow today's currency. A later currency
correction could make that label false. Values are grouped without an inferred
currency, with an explicit note; the original/current comparison can use each
payload's own currency. This is a deliberate accuracy-over-polish trade-off.

## Important rendering and security choices

`TechnicalDetails` uses native `<details>` so complete evidence is closed initially
and works with browser keyboard behavior. JSON is pretty-printed from the original
object. This preserves JSON values, including decimal strings and nulls; it does not
claim byte-for-byte preservation of network whitespace or property serialization.
Colored tokens are React text inside spans. There is no `dangerouslySetInnerHTML`,
HTML parsing, Markdown execution or model-supplied component code.

Clipboard permissions vary. Copy reports success only after `writeText()` resolves;
denial yields an explicit message and Select JSON selects the exact preformatted
text for the browser's manual Copy command. These are local UI states, not API
mutations. The live status is attached to its own disclosure.

`EvidenceValue` handles null, strings, numbers, booleans, arrays and nested objects.
It uses field context to distinguish currency amounts from quantities and dates.
Known arithmetic-rule expected/observed values can use money context; generic
unknown data is not guessed to be money. Recursion in the readable view stops at
five levels to avoid an unusable nested layout; **the full technical JSON is never
truncated**. Unknown future data remains inspectable even without custom prose.

Source snippets are untrusted, unverified text. No confidence score, authenticity
badge or page citation is invented. Absence of reported uncertainty is explicitly
not verification. Existing terminal/read-only controls are untouched.

## Independent modification recipes

- **Rename a rule:** update only `ruleLabels`, add/update a unit expectation, run
  unit tests. Never change the backend code/severity to improve a label.
- **Add an audit type:** inspect actual server details, add a switch case and a
  test with realistic/missing fields. Keep generic fallback and full original event.
- **Change the original summary layout:** edit OriginalExtraction and scoped CSS.
  Keep `original` and `current` separate and don't replace missing values with zero.
- **Add a new readable evidence structure:** teach EvidenceValue a narrowly scoped
  field format or make a small typed display component. Keep unknown nested data in
  technical details rather than inventing facts.
- **Change copy behavior:** edit TechnicalDetails only; test denial and successful
  copying before changing callers. Never persist auth or financial contents to
  localStorage merely to make copying convenient.
- **Adjust density:** change evidence-scoped padding/type rules; keep money readable
  and contained scroll regions. Do not shrink text to fit every line horizontally.
- **Add future AI evidence:** reuse display primitives after the real API exists.
  Clearly separate advisory findings from existing human decisions. This guide does
  not authorize that implementation.

Keep formatters **one-way**. A common mistake is to reuse a pretty money string as
an input value, then submit `"2,300.00"` to an API expecting `"2300.00"`. R1 leaves
all editor values and requests alone precisely to avoid that coupling.

## Tests and execution

From `frontend/`, on Windows:

```powershell
npm.cmd run test:unit
npm.cmd run typecheck
npm.cmd run test:e2e
$env:PUBLIC_PREVIEW='true'
npm.cmd run test:e2e -- --config playwright.public.config.ts
```

Unit tests use Playwright's existing TypeScript transformer/assertions but launch
no browser, API or database. They cover high-magnitude/trailing-zero currency data,
JPY, missing/invalid values, rule priority, event mappings, immutable inputs and all
actual public fixture event/rule codes. Do not read “mock” fixtures as AI accuracy.

The operator suite creates/cleans a random test schema and performs real API
financial workflows there. It does not mutate the owner's existing demo schema.
Its R1 assertions reconstruct the actual 2500.00→2300.00 diff, recorded actor/reason,
original/current comparison and current-revision approval. Existing duplicate,
CSV, supplier and mobile behavior remain covered.

Public tests run against the frozen synthetic API, verify hidden write controls,
403 public mutation denial, collapsed payloads, source JSON value equality, copy
denial/manual selection, missing extraction and unknown HTML-like evidence. The
unknown event is injected into a browser response only, never inserted into audits.
Do not claim it is a real financial record.

Production local builds and backend regression from the root:

```powershell
docker compose exec -T backend python -c "import os,pytest; os.environ['TEST_DATABASE_URL']=os.environ['DATABASE_URL']; raise SystemExit(pytest.main(['-q','--tb=short','-p','no:cacheprovider']))"
docker compose --profile dashboard up -d --build --no-deps frontend
docker compose -f infrastructure/compose.public.yml up -d --build --no-deps dashboard
node docs/ui-ux/tools/r1-capture.mjs after
```

The local production builds run Next.js static export inside the existing Docker
build and serve the output with nginx. Both API build-time URLs must work. No cloud
service is deployed. Captures use four viewports and read existing records without
submitting writes. Do not run the `before` capture after implementation and call it
a baseline; the actual pre-change capture is already retained separately.

See [R1 progress report](R1_PROGRESS_REPORT.md) for exact counts, failures, warnings,
screenshots, known limitations and the manual review checklist.

## Owner exercises

1. Explain why `financial("9999999999999999.99", "USD")` is safe while converting
   it through a JavaScript number is not. Add a trailing-zero case to the unit test.
2. Trace one correction from the server's `diff` through `auditView()`, then
   EvidenceValue and the rendered table. Identify which file owns financial writes.
3. Add a harmless unknown event to a local test. Confirm it remains visible and
   its complete details can be copied without adding a backend event type.
4. Change “Invoice total” to a clearer label and demonstrate that no validation or
   posting service needs a change. Revert the label if it obscures the rule meaning.
5. Deny clipboard access, select JSON manually, and explain why display adapters
   must not destroy evidence when a convenience API is unavailable.

The engineering lesson is separation of concerns with preserved provenance:
backend facts and authority stay fixed; small, testable view models improve how
people understand those facts. R1 stops here. R2 requires explicit approval.
