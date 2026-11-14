# Redesign implementation roadmap — approval required

This roadmap does not authorize implementation. Current work stops at the audit,
design system and isolated concepts. It does not advance the AI roadmap's Day 6.
After the owner selects a direction, implement one bounded UI package at a time.
Prefer Theme B. No runtime dependency or backend change is needed for the first
packages. Effort below is relative, not a promised schedule.

## Prioritized backlog

| Package | Priority / effort | Work | Dependency | Acceptance evidence |
|---|---|---|---|---|
| R1: readable financial evidence | Critical / medium | Human audit timeline, original summary, neutral validation labels, collapsed passes, complete technical disclosure | Owner approves design; existing typed responses | All event types safe, original/current distinction, copy fidelity, failed checks still visible |
| R2: accessible foundations | High / medium | Semantic tokens, readable type, contrast, focus, native inputs, common buttons/tables/notices, correct tabs/nav | Theme approval; relevant installed Next.js guides before framework edits | Keyboard route, screen reader spot-check, contrast, all four viewports, 200% zoom |
| R3: review workspace and actions | High / medium | Source/current/evidence grouping, staged next action, dirty/conflict guidance, explicit reject/post confirmation | R1/R2; unchanged revision and action requests | Clean and exception workflows pass isolated tests, original audit unchanged |
| R4: worklists and overview | High–Medium / medium | Exception-first overview, visible issue explanation, compact result list, preserved filters/page, mobile summary rows | R2; existing list/stats contracts | Correct counts, no invented metrics, mobile state/action visible, loading/zero/error distinct |
| R5: suppliers, ledger and intake polish | Medium / small–medium | Plain policy wording, list search where local, supported registration feedback, CSV scope, direct upload result | R2; existing GET/POST contracts | No new supplier-edit claim; export matches posted snapshots, upload errors/repeats usable |
| R6: advanced presentation refinements | Low / small | Refined icons, optional density preference, source pane sizing, dark exploration | Operator feedback on R1–R5 | Measured benefit; no typography shrink, no inaccessible preference control |
| F1: investigation UI | Future, separate AI authorization | Evidence/recommendation/run timeline and stale states | Actual Phase 2 contracts, auth, event persistence, Day 14 scope | Advisory-only, scoped citations, no financial-write tool, stale/cancel/failure tests |
| F2: technical observability UI | Future, separate authorization | Redacted traces, calls, usage and evaluation views | Actual stored telemetry, cost inputs, authorization decision | No invented usage or role claim; no external tracing without consent |

### Quick wins within an approved R1/R2

Use a neutral lookup map for rule names, improve muted text contrast, increase
table text to 14px, replace “decimal string”, label technical disclosures consistently,
add active navigation semantics and a skip link. Keep complete original codes under
details. These have small implementation surface but still require the owner's
approval under this audit-only request.

## R1: readable evidence — first recommended implementation

Extract pure presentation functions and read-only components from detail, keeping
data fetching, financial requests and state checks intact initially. Audit adapter
maps actual event type and details to title, sentence, actor/time, transitions,
field diff and notes. Unknown types retain a generic title plus complete payload.
Do not rewrite audits, classify the actual actor incorrectly or remove repeated
events. Do not parse arbitrary nested evidence as executable HTML.

Original extraction uses a structured supplier/invoice/date/line/amount/evidence
summary with explicit missing/uncertain values and unverified label. Current data
and approval are separate sources. Technical view renders the exact object values
from the backend; pretty-printing is allowed, destructive normalization is not.
Copy exact decimal strings and nulls; clipboard denial has a selection fallback.

Validation adapters show Passed / Warning / Blocks posting, neutral labels and
typed expected/observed values, with full raw evidence under details. No floats
for money, no new rules, no weaker severity or inferred approval.

R1 acceptance:

- Wrong total shows recorded USD 2500.00, expected USD 2300.00 and blocked state,
  with instruction to verify source rather than auto-correct.
- Existing correction shows stored 2500.00 → 2300.00, actual actor/reason/time and
  revision. Approval and ledger events remain distinct.
- Raw codes, UUIDs, hashes and attempt IDs are collapsed by default, fully
  accessible and copyable; JSON equality test protects exact payload values.
- “Invoice date range — Passed” replaces negative-code wording; blocker priority
  and all original rule outcomes/severities remain unchanged.
- No invoice/approval/ledger audit row changes from reading these views.
- All common, unknown, missing-data and null payload types render safely.

## R2/R3: components and safe decision interaction

Move tokens into a single semantic file mapped to Tailwind; consolidate existing
Heading/Badge/Notice/Pager and repeated table/form styles. Keep `InvoiceTable` shared
but allow a smaller overview subset. Introduce complete tab semantics or ordinary
links rather than incomplete ARIA. Prefer native controls over adding a UI library.

Keep frontend gating aligned with actual state, dirty flag, current validation,
blockers, current-revision human review requirement, pending state and terminal
status. This prevents avoidable rejected requests but does not authorize posting;
the backend always rechecks. Confirmation names invoice, exact currency/amount,
revision and terminal consequence. A rejected or posted invoice stays immutable.
No optimistic “posted” result before backend confirmation. No automatic retry of
approve/post after a conflict, timeout or stale snapshot.

Acceptance: clean explicit post, held totals blocked, corrected save→revalidate→
required current approval→post, duplicate reasoned reject, stale 409 recovery,
read-only public hidden controls, protected original download, disabled/pending
feedback and keyboard focus recovery. Test each in isolated synthetic schemas,
never against the owner's existing financial records.

## R4/R5: worklists and supporting screens

Use current API counts, not hardcoded dashboard figures. A ready count means no
current blockers, not verified authenticity. Keep failed extraction discoverable
even though it is not NEEDS_REVIEW. Preserve rejected status and currency-separated
ledger values. No single mixed-currency “money saved” metric. Make upload dedupe
result a link and public empty-state instructions achievable.

Supplier search may be client-side for the existing finite response; supplier
updates, date-ranged reporting, cross-invoice comparison richness and evidence
retrieval require separate API decisions. Do not invent controls that appear to
work. The existing CSV is all posted entries, not a filtered front-page export.

## Test strategy and stop conditions

1. **Pure adapters:** event title/actual actor mapping, diff/null/unknown types,
   neutral rule labels, escaped evidence, exact monetary strings and JSON equality.
   These tests protect meaning, not CSS snapshots that mirror implementation.
2. **Browser UI:** reuse existing Playwright infrastructure. Keep operator suite
   schema isolation and cleanup. Add meaningful assertions for timeline, source
   comparison, current revision/next-step, copy denial, keyboard and mobile action
   visibility. Public tests must still prove readonly behavior; denial tests only
   against isolated public fixture mode, not private existing records.
3. **Backend regression after real implementation:** run existing complete
   PostgreSQL suite and operator/public browser scenarios. Baseline report says
   181 backend and 2+1 browser cases; these are historical counts, not newly
   executed for this audit. Report actual counts from the new run.
4. **Build compatibility:** TypeScript and Next.js static export with both API
   URLs; preserve query detail route, source blob lifecycle and mode config.
5. **Accessibility:** measured color pairs, keyboard order/tab behavior, dialog
   trap/return/Escape, names/statuses, 200% zoom, 320px reflow, screen-reader check.
   A future automated accessibility dependency requires justification; no formal
   accessibility scanner is claimed in this audit.
6. **Visual acceptance:** real before/after captures at the four specified sizes.
   Check exact amount/state/action remains visible, long names/notes, empty/error/
   pending states, blocked and terminal forms. Screenshots stay ignored if private.

Stop if data precision changes, original payload evidence is lost, terminal rows
become editable, frontend implies approval/posting authority for AI, public writes
appear, financial regression fails or migration compatibility breaks. Resolve
before proceeding; do not bypass these failures by disabling controls/tests.

## Future AI acceptance gates

Do not ship investigation navigation until actual endpoints and reports exist.
Run status and invoice status remain separate. Reports display revision/hash/batch
applicability and evidence provenance, including contradictions and missing evidence.
Parallel task timeline comes from actual events. Retry/cancel/checkpoint recovery
is shown only after implemented. Tokens/cost are Unknown when unavailable; estimated
cost requires a dated pricing input. No progress percentage fabricated from graph
nodes. AI proposal cannot approve, register supplier, correct or post.

Use the existing Phase 2 roadmap order and require separate authorization per
milestone. This UI roadmap neither implements nor skips Days 6–16.

## Owner review and handoff

Open `design-preview/index.html` locally; compare wrong-total exception, original
extraction and timeline under A/B/C, on desktop and mobile. Theme B is recommended.
The first implementation approval should name **R1 readable evidence** and any
desired theme changes. Application changes remain pending explicit approval.
No deployment, public exposure, financial write, new repo or Git push is part of
this audit delivery.
