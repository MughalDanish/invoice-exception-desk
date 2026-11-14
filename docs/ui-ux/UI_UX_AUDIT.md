# Invoice Exception Desk: UI/UX audit

Inspected locally on 14 November 2026. Baseline: `3249bf1`, branch
`feature/agentic-invoice-investigation`. This deliverable is an audit and design
proposal. Application components, APIs, financial records and Phase 2 functionality
were not changed. Product specification instructions describe the product; the
current user request explicitly limits this execution to inspection and concepts.

## Executive assessment

The application has a coherent, restrained visual identity and a usable end-to-end
financial workflow. Its strongest product feature is the explanation of why an
invoice cannot post. Its weakest experience is reading that explanation: small,
low-contrast text, implementation terminology, long successful-check lists and
expanded technical audit payloads make an operator work too hard to find the issue.

Recommend **Theme B: Financial Intelligence**, preserving the existing forest/teal
character while replacing technical-first information structures. Prioritize the
activity timeline, structured original extraction, neutral validation names,
contrast and revision-specific action guidance before a broad visual refresh.
Do not add charts, AI progress, savings or confidence metrics without real data.

Overall editorial assessment: **5/10**, a rounded assessment of the areas below,
not an empirical usability score. No customer usability study was performed.

## Inspection method and evidence

- Chromium through the existing local Playwright installation. Reused the
  credential handling and selectors from `scripts/check_dashboard.mjs` and
  inspected both acceptance suites/configurations. No new dependency installed.
- `http://localhost:3000`: authenticated private operator workspace. Four existing
  invoices: two posted, one ready, one rejected; zero current review exceptions.
- `http://localhost:3002`: anonymous read-only demo. Fifteen invoices: nine held,
  four ready, one posted, one extraction failure. These are different datasets,
  not inconsistent counts within one workspace.
- Logged in using ignored local configuration in memory. No credentials included
  in reports, previews or console output. Login inputs and top-bar identity masked
  in captures. No request traces, HAR or authorization headers recorded.
- Final main audit: **196 distinct full-page PNG captures**, 49 screen/state
  combinations at 1440×900, 1280×800, 768×1024 and 390×844. See ignored
  `storage/ui-audit/evidence.json` for computed styles, dimensions and exact files.
- Browser routing allowed GET/HEAD/OPTIONS only for application APIs. No upload,
  processing, correction, review, supplier creation or posting request was sent.
  CSV was downloaded with an existing GET and retained only in ignored storage.
- Before/after statistics, ledger and supplier responses were identical for both
  modes. No uncaught browser page errors in either complete pass.
- API loading and 503 error views were reproduced through local request
  interception. They are explicitly simulated UI states, not observed outages.
- Sources reviewed: original specification, architecture, Day 1–5 reports, all
  six Phase 2 documents, desk/list/detail/ledger/supplier components, API transport,
  CSS, static export routes and browser tests. Historical test results are not
  represented as new test executions.

The reproducible read-only capture tool is [tools/audit.mjs](tools/audit.mjs).
Screenshots are intentionally ignored, not portable repository assets. Links below
work in this checkout after capture; regenerate them on another machine.

## Verified findings and priorities

| ID | Verified finding | Business consequence | Priority |
|---|---|---|---|
| U01 | Every audit event renders `JSON.stringify(event.details)` in an expanded `pre`; generic state titles | Hard to reconstruct decisions or identify an important correction | Critical |
| U02 | Original extraction is already collapsed, but opening it reveals only JSON | No readable original/current comparison | High |
| U03 | Rule headings use `title(rule_code)`, including “Invalid date range — Passed”, “Unapproved vendor — Passed” | A passing control can sound like a failed condition | High |
| U04 | Several 8–12px text styles and measured normal-text contrast below 4.5:1 | Effort and reading errors during review | High |
| U05 | All passed rules expand; source/editor precede rule detail | Blocking explanation appears far down a long page | High |
| U06 | All five correction/review/post buttons share one wrapping action group; gating reasons appear in a single footnote | Current next step is harder to identify | High |
| U07 | Mobile tables scroll internally; status and review link fall off screen | Operator sees amounts without readily visible decision state | High |
| U08 | Tabs lack panel association and arrow-key behavior; active nav lacks `aria-current`; no skip link | Less predictable keyboard and assistive navigation | High |
| U09 | Issue codes appear in native title tooltips, JSON remains in rule expected/observed and error codes append to messages | Technical concepts escape into routine reading | Medium |
| U10 | Overview repeats full invoice table and an eight-event activity list | Main work queue competes with volume and repetitive events | Medium |
| U11 | Supplier form says “Amount limit (decimal string)”; policy list has no search or edit workflow | Implementation term and limited discoverability | Medium |
| U12 | Generic empty text suggests upload even in the public read-only view | Visitor receives an impossible instruction | Medium |

“Critical” here means central task comprehension, not a demonstrated ledger or
authorization vulnerability. No financial safety failure was discovered or
injected by this non-mutating audit.

## Screen-by-screen review

Ratings use five equally weighted dimensions, each 0–2: **C** task clarity,
**R** readability, **W** workflow guidance, **A** accessible interaction,
**S** small-screen use. 0 = materially weak, 1 = partial, 2 = strong in inspected
conditions. Scores are transparent designer judgments; they do not certify WCAG
conformance or measure operator completion times.

### 1. Login — 6/10 (C2 R1 W1 A1 S1), Medium

Purpose: enter the private operator workspace. Clear labels, autocomplete and a
distinct submit button work; the story panel dominates the mobile first view.
The `.env` and API-address instructions target developers rather than accountants.
Evidence: [desktop](../../storage/ui-audit/private-login-desktop.png),
[mobile](../../storage/ui-audit/private-login-mobile.png).

Propose a shorter workspace identity above the form, “Sign in” as primary action,
and a collapsed local-setup help section. Preserve password-manager support and
memory-only session behavior. Add focus-linked error feedback and a reveal-password
control only if requested during implementation. Stack form before secondary story
on mobile, retain visible labels and 44px targets. Benefit: faster access with less
setup jargon. Do not imply production SSO or password recovery exists.

### 2. Overview — 6/10 (C1 R1 W2 A1 S1), Medium

Purpose: identify what needs action today. Five KPI cards, a review banner and
currency-separated posted totals are useful. The four-row private page is still
1696px high at desktop; the public overview is 2559px high with 15 rows. Repetitive
“Duplicate upload returned” events occupy the activity card; no invoice identity
appears in those event titles.
Evidence: [private](../../storage/ui-audit/private-overview-desktop.png),
[public mobile](../../storage/ui-audit/public-overview-mobile.png).

Prioritize review workload, ready invoices and recent decisions. Show a short
worklist with an explicit “View all”, rather than a second full invoice-management
screen. Keep rejected/extraction failures discoverable and totals by currency.
Use linked cards only with accessible names; maintain visible count labels. Two
columns of readable cards on mobile, a one-column action strip. Benefit: next work
is apparent without adding fictional charts or date-range metrics unsupported by API.

### 3. All invoices — 6/10 (C2 R1 W1 A1 S1), High

Purpose: locate and open an invoice. Search, server filtering and pagination work.
The 11px cells, 9px headers, generic “Review” links and tooltip-only issue codes
reduce scanability. Mobile table width is 759px inside a 356px viewport container.
Evidence: [desktop](../../storage/ui-audit/private-invoices-desktop.png),
[mobile](../../storage/ui-audit/private-invoices-mobile.png).

Use 14px rows, explicit current exception descriptions and unique accessible link
names. Keep supplier/invoice, amount, status and action first. Retain native selects
initially, add clear-filter feedback and preserved query state on return. Name the
scroll region; use focusable horizontal scrolling. On phones use an invoice summary
row/card with status and review link always visible, with secondary dates disclosed.
Benefit: identify the right record with fewer scrolls. Do not hide failed checks
merely because their codes are technical.

### 4. Upload — 6/10 (C2 R1 W1 A1 S1), Medium

Purpose: safely submit a supported synthetic document. Inline form explains types,
8 MiB limit and mock fixtures. No dedicated upload screen or modal exists. Selecting
and submitting a file was deliberately not performed against application data.
Evidence: [desktop](../../storage/ui-audit/private-upload-desktop.png),
[mobile](../../storage/ui-audit/private-upload-mobile.png).

Keep a simple inline form or accessible drawer. Emphasize file name/type/size and
the mock-mode fixture restriction, then one upload action. Show received/extracting/
validation states truthfully, with a direct link to the returned invoice, including
existing-file deduplication. Announce pending/result text; focus errors; mobile
stack controls. Benefit: no searching for a result after processing. No fake
percentage progress; keep server MIME, dedupe and size checks authoritative.

### 5. Invoice detail shell — 5/10 (C1 R1 W1 A1 S1), High

Purpose: compare a source, understand a hold and make a controlled decision. Existing
two-column layout and revision label provide a foundation. A clean detail is
approximately 3010px high; its important validation context is below the editor.
Evidence: [ready invoice](../../storage/ui-audit/private-detail-clean-004-ready_to_post-desktop.png),
[held invoice](../../storage/ui-audit/public-detail-wrong-total-needs_review-desktop.png).

Header: invoice/supplier/total/status/revision, then a blocker summary and next
required step. Desktop: resizable-in-future source/evidence column beside readable
current information; no resize library now. Put failed checks before secondary
metadata. Use Review, Original, Activity navigation with full keyboard semantics.
At tablet/mobile put blocking facts before a collapsible source preview, maintaining
source access while editing. Benefit: orient the operator before a long form.

### 6. Original document preview — 6/10 (C2 R1 W1 A1 S1), Medium

Purpose: verify facts against the uploaded file. Protected download and titled iframe
exist; file fingerprint is already collapsed, a good disclosure pattern. Headless
Chromium screenshots show a gray PDF region; this does not prove the PDF is broken
in an interactive browser. Do not substitute a fake document rendering.
Evidence: [source region](../../storage/ui-audit/private-detail-clean-004-ready_to_post-desktop.png).

Always expose “Open original”/download adjacent to preview, its filename and a real
loading/error fallback. Keep hash/source IDs under technical details. Size source
pane relative to viewport rather than fixed 620px on all desktops. On mobile collapse
preview by default after showing source identity; preserve keyboard access and
accessible iframe title. Benefit: less wasted space and a usable fallback when a
browser cannot render PDFs. PDF content accessibility was not assessed.

### 7. Extracted information and original extraction — 4/10 (C1 R1 W0 A1 S1), High

Purpose: distinguish what the extractor saw from what humans currently saved.
Current fields are editable/read-only by state; the preserved original is only a
JSON block. Original and current total differ on the existing corrected invoice,
but there is no field-level comparison in the default review screen.
Evidence: [corrected current](../../storage/ui-audit/private-detail-wrong-total-posted-desktop.png),
[original JSON](../../storage/ui-audit/private-detail-wrong-total-posted-original-desktop.png).

Use read-only supplier/date/currency summary, line-item table, subtotal/tax/total,
evidence snippets and uncertain/missing fields for original output. Add an explicit
“Original extraction / not verified” label. A “Current saved” view must remain
distinct from “Human approved revision N”. Link actual correction diffs and review
records, never infer verification from absence of uncertainty. Collapse exact source
JSON with syntax color and copy/selection fallback. Tabular numerals, decimal-string
formatting and contained line-table scroll on mobile. Benefit: compare facts without
decoding a payload. No confidence score, inferred address or invented tax ID.

### 8. Validation checks — 4/10 (C0 R1 W1 A1 S1), Critical

Purpose: explain whether posting is blocked and what needs examination. Failure-first
sorting and expected/observed data are strengths. Names state failures even when a
check passes; nested JSON and every expanded passing rule lengthen the screen.
Evidence: [total hold](../../storage/ui-audit/public-detail-wrong-total-needs_review-desktop.png),
[date hold](../../storage/ui-audit/public-detail-missing-invoice_date-needs_review-desktop.png).

Use neutral business labels: “Invoice date range”, “Supplier approval”, “Invoice
total”, “Duplicate identity”. Show Passed / Warning / Blocks posting explicitly,
including warning severity even when no blocker exists. Show failed-count summary,
typed expected/observed comparisons and a source-verification next step. Successful
checks collapse under their count. Keep original code and full evidence in details.
Stack comparisons on phones; text plus icon, never color alone. Benefit: understand
the hold before changing a value. Change no rule, severity or rounding behavior.

### 9. Exception queue — 5/10 (C1 R1 W1 A1 S1), High

Purpose: prioritize held invoices. Current view is the same table restricted to
NEEDS_REVIEW; public filters expose actual examples, private queue is empty.
Evidence: [public](../../storage/ui-audit/public-exceptions-desktop.png),
[private empty](../../storage/ui-audit/private-exceptions-desktop.png).

Add a primary exception description and “Resolve” entry, preserve issue filter and
queue position when returning from detail. Distinguish held invoices from extraction
failures so neither disappears: a separate failed-processing filter/worklist is
appropriate; do not change status semantics. On mobile show exception and state
beside invoice identity. Name all filters and announce result counts. Benefit:
operators can prioritize actual holds instead of interpreting counts/tooltips.

### 10. Correction and review form — 5/10 (C1 R1 W1 A1 S1), High

Purpose: save an intentional correction and revalidate the exact revision. Current
field labels exist; all date/money inputs are plain text and source uncertainty is
an editable comma-separated developer-like list. Buttons wrap after the long editor.
Evidence: [editable ready invoice](../../storage/ui-audit/private-detail-clean-004-ready_to_post-desktop.png).

Group supplier, identity/dates, amounts, lines and source evidence. Explain fractional
tax input with an example, date format, missing values and currency precision.
Show original/current diff and dirty state before saving; preserve unsaved edits or
ask before navigation when necessary. Notes explain why, not merely what. Field
errors associate with inputs; a single next-step summary explains revalidation.
Stack groups, retain numeric keyboard hints without converting money to floats.
Benefit: deliberate corrections with fewer avoidable stale-action errors.
Saving and revalidation were not invoked during this audit.

### 11. Approval, rejection and posting — 5/10 (C1 R1 W1 A1 S1), High

Purpose: make an explicit authorized decision. Existing disabled buttons and backend
revision checking are essential. A ready invoice displays five actions together;
rejection notes are required, but there is no separate confirmation interaction.
Source shows the post button can be enabled while a corrected revision still needs
approval; backend will refuse it. This branch is source-confirmed, not live-created.
Evidence: [ready actions](../../storage/ui-audit/private-detail-clean-004-ready_to_post-desktop.png),
[terminal state](../../storage/ui-audit/private-detail-duplicate-altered-rejected-desktop.png).

One primary next step: Save, Revalidate, Approve current revision, then Post according
to actual requirements. Keep clean-invoice policy intact; do not require approval
where backend does not. Show blocker/stale/dirty explanations beside actions.
Separate Reject behind reason entry and an accessible confirmation that names the
invoice and irreversible terminal result. Confirm posting amount, currency and
revision; no payment language. On mobile use an unobscured action region; dialogs
must restore focus and support Escape. Benefit: fewer ambiguous or accidental
decisions. No decision submission, destructive test or success fabrication occurred.

### 12. Audit history — 3/10 (C0 R1 W0 A1 S1), Critical

Purpose: reconstruct who did what and why. Records are present and immutable, but
default JSON contains hashes, state constants, batch IDs and attempt IDs. The
existing corrected invoice audit is **5387px** high at 1440px viewport width.
Evidence: [correction history](../../storage/ui-audit/private-detail-wrong-total-posted-audit-desktop.png),
[clean history](../../storage/ui-audit/private-detail-clean-001-posted-audit-desktop.png).

Use event-specific icon/title, actor as actually recorded, localized timestamp with
timezone, status chips and human-readable sentence. Show corrections as field /
before / after; preserve notes and decisions verbatim as escaped text. Validation
shows blocker summary; posting shows exact amount/currency. Collapse full original
event JSON with copy. Unknown types use a safe generic title and complete payload.
Do not relabel recorded operator as “AI” or “System” merely because an event sounds
automated. Group repeated intake events only with an explicit count and access to
every event. Semantic ordered list, readable wrapping on phones. Benefit: trace an
actual decision without losing evidence or editing audit rows.

### 13. Ledger and CSV — 7/10 (C2 R1 W2 A1 S1), Medium

Purpose: inspect immutable posted snapshots and export them. Clear table, invoice
links and existing CSV download work; small time/operator text and generic View
links remain. No ledger edits are offered, appropriately.
Evidence: [desktop](../../storage/ui-audit/private-ledger-desktop.png),
[mobile](../../storage/ui-audit/private-ledger-mobile.png).

Show exact amount/currency, posting time with zone, actor and invoice. Keep export
in ledger context and label scope “Posted entries”; explain whether an export is all
records rather than just the current page. Do not invent date/search API filters.
Keep formula defenses and snapshot-based export unchanged. Mobile rows retain
amount/status/invoice action; name download outcome via status. Benefit: export
scope is predictable and historical values remain trustworthy.

### 14. Supplier management — 6/10 (C2 R1 W1 A1 S1), Medium

Purpose: inspect approved supplier policies and register an authorized supplier.
Native labels and explicit approval checkbox work; “decimal string” and “Know your
suppliers” are less direct than “Suppliers”. Only list/add exists; no update screen.
Evidence: [registry](../../storage/ui-audit/private-suppliers-desktop.png),
[form mobile](../../storage/ui-audit/private-supplier-form-mobile.png).

Use Supplier name, Currency policy, Review threshold and Approval status. Explain
limit/currency dependency near fields and that registry approval does not approve
an invoice. Add client search for the existing finite list if needed; show policy
details without fictional edit buttons. Mobile stacked form, labels/errors, large
checkbox target. After real registration, link back to held invoice for revalidation
and current-revision review. Benefit: safer policy interpretation. Updating existing
suppliers needs a separately authorized backend contract and is outside this redesign.

### 15. Navigation and shell — 6/10 (C2 R1 W1 A1 S1), Medium

Purpose: orient the operator across work, reference and history. Current five-section
navigation is compact and coherent; active item is CSS-only, tiny mobile horizontal
links compete with page content and there is no skip link.
Evidence: [tablet](../../storage/ui-audit/private-overview-tablet.png),
[mobile](../../storage/ui-audit/private-overview-mobile.png).

Keep Overview, Invoices, Exceptions, Ledger, Suppliers. Add accessible active state,
skip-to-main and named navigation. Use consistent line icons with text labels rather
than unrelated Unicode glyphs; no new icon library is required. Tablet gets a
compact rail/drawer; mobile a labeled menu or reachable primary links, not hidden
financial actions in an overflowing tab strip. Retain explicit read-only/synthetic
mode distinction. Benefit: orientation without new product complexity.

## Accessibility and responsiveness

Computed/source color pairs, using WCAG sRGB relative luminance:

| Existing text / background | Ratio | Observation |
|---|---:|---|
| `#73807B` / white | 4.12:1 | Normal muted text below 4.5:1 |
| `#8A9389` / white | 3.17:1 | 9px KPI explanation below 4.5:1 |
| `#899185` / `#FAFBF8` | 3.13:1 | 9px table header below 4.5:1 |
| `#849278` / `#F5F6F2` | 3.04:1 | Inactive small tab label below 4.5:1 |

No mandatory minimum font size is attributed to WCAG; 14px tables and 12px metadata
are proposed product rules. Existing labelled inputs, visible focus outlines,
titled iframe and `role=status/alert` are positives. Disabled native controls have
different contrast requirements; low-contrast disabled inputs are not automatically
reported as WCAG failures. Generic Review/View link names need invoice context.

All 196 captures had `documentElement.scrollWidth <= innerWidth`. This proves
containment only. Internal table scrolling remains necessary; tablet at 768px keeps
a 175px sidebar, limiting content; source preview precedes critical review data in
a single long mobile column. No zoom, screen reader or real touch-device study was
performed. Browser keyboard probes and console inspection are reported separately
in [verification](VERIFICATION.md); do not infer conformance from screenshots.

Reference checked through Firecrawl: [W3C WCAG 2.2 quick reference](https://www.w3.org/WAI/WCAG22/quickref/).
Relevant criteria: 1.4.3 contrast, 1.4.10 reflow (two-dimensional data tables have
exceptions), 2.1.1 keyboard, 2.4.1 bypass blocks, 2.4.7 visible focus, 2.4.11 focus
not obscured, 2.5.8 target size minimum (24 CSS px with specified exceptions),
4.1.2 semantics, 4.1.3 status messages. Proposed 44px mobile targets exceed the
24px minimum; small link height alone does not establish failure without spacing
and exception analysis.

## Journeys and state coverage

| Journey | Friction found | Proposed change | Safety boundary |
|---|---|---|---|
| A: clean invoice | Upload result requires finding row; checks/actions separated | Direct result link, concise check summary, explicit Post | Fresh server checks; no automatic posting |
| B: incorrect invoice | Original JSON; generic rule name; five competing actions | Side-by-side original/current, failed-rule evidence, staged next step | Save → revalidate → required current approval → explicit Post |
| C: duplicate | Count/tooltips and JSON references; no obvious prior-invoice comparison | Compare supplier/number/amount with links when authorized response supplies IDs | Never treat equal amount as required for duplicate detection; no override |
| D: historical activity | Expanded internals bury important changes | Human timeline, before/after, notes and provenance disclosure | No edit, removal or fabricated actor |
| E: suppliers | Technical amount wording; no search; no edit capability | Plain policy fields, searchable finite list, return to held invoice | Existing authorized add only; updates require new contract |

Populated, empty, read-only, terminal, disabled, loading and error screens were
captured. Existing corrections/decisions were read from history. No successful
mutation was reproduced. Running extraction and received-only states were not
available in the current datasets; attempting to create them would change records.
Approval/rejection dialogs, drawers, rich tooltips, toasts and skeletons do not exist
today; they are recommendations, not inaccessible working screens. Native selects,
inline upload/add forms, evidence/file disclosures and both detail tabs were inspected.
No production AI investigation or observability screen exists.

## Deliverables and next decision

See [theme comparison](THEME_COMPARISON.md), [design system](DESIGN_SYSTEM.md),
[information architecture](INFORMATION_ARCHITECTURE.md),
[redesign roadmap](UI_REDESIGN_ROADMAP.md), and the
[standalone theme gallery](design-preview/index.html).
Application redesign and Phase 2 implementation remain unstarted pending explicit
owner approval.
