# Proposed design system: Financial Intelligence

Status: recommendation and standalone concepts only. No production token or
component has been edited. [Theme B preview](design-preview/theme-b.html).

## Foundations

Use semantic CSS custom properties rather than hard-coded shades throughout
components. Tailwind 4 is already installed; extend its existing token mapping
after approval, with no new CSS framework or UI package.

```css
/* Proposed production mapping, not applied to frontend/src. */
:root {
  --color-canvas: #F5F6F3;
  --color-surface: #FFFFFF;
  --color-surface-subtle: #EFF3EF;
  --color-text: #172D27;
  --color-text-muted: #52675E;
  --color-action: #155E51;
  --color-action-hover: #10483E;
  --color-on-action: #FFFFFF;
  --color-accent: #795B25;
  --color-sidebar: #112F2A;
  --color-sidebar-text: #DCEAE4;
  --color-sidebar-active: #28483F;
  --color-border: #D5DED8;
  --color-input-border: #64748B;
  --color-focus: #1D4ED8;
  --color-success: #166534;
  --color-success-surface: #F0FDF4;
  --color-warning: #854D0E;
  --color-warning-surface: #FFFBEB;
  --color-error: #B91C1C;
  --color-error-surface: #FEF2F2;
  --color-info: #1D4ED8;
  --color-info-surface: #EFF6FF;
  --radius-control: 6px;
  --radius-panel: 8px;
  --shadow-panel: 0 2px 6px #112F2A08;
  --shadow-overlay: 0 12px 32px #112F2A1F;
}
```

Do not use subdued decorative borders as the only visible form-control boundary.
Disabled controls keep legible values; prefer plain read-only descriptions over a
wall of disabled inputs in finalized/public views. Status semantics are independent
of extraction provider or brand accent. Successful arithmetic is not authenticity
or human approval.

| Type role | Size / line height | Weight | Usage |
|---|---|---|---|
| Page title | 32 / 38px; mobile 28 / 34px | 600 sans; concept's Georgia 500 optional | One h1 |
| Section | 18 / 26px | 600 | Panels and major groups |
| Subsection | 15 / 22px | 600 | Evidence, rules |
| Body and table | 14 / 21px | 400; amounts 600 | Default reading |
| Field label | 13 / 18px | 600 | Always visible |
| Metadata | 12 / 18px | 400 | Actor, time, secondary identifiers |
| Eyebrow | 11 / 16px | 600 | Decorative orientation only |
| Technical code | 12 / 20px | 400 Consolas/monospace | Collapsed technical details |

Default Segoe UI, Arial, sans-serif avoids network fonts and installation. Evaluate
self-hosted Source Sans 3 only if it improves real reading; it is not a dependency
of these concepts. Financial cells use `font-variant-numeric: tabular-nums`, right
alignment and currency codes. Preserve decimal strings and currency-specific scale.
Never pass financial values through `Number`, `parseFloat`, `toFixed` or a formatter
that silently changes precision. A future thousands-separator helper must operate
on the string and be tested for USD/EUR/GBP/JPY, null, negative and invalid values.
Tax rate is a fraction, distinct from money; display exact fraction with a clearly
derived percentage only if lossless conversion is implemented.

Spacing tokens: **4, 8, 12, 16, 20, 24, 32, 40, 48, 64px**. Use 20–24px panel
padding, 16–20px related-group gaps and 32px between major sections. Do not increase
page height to make small type feel premium. A dense row changes padding, not font
size. Control heights 40px desktop, 44px mobile; icons 16px inline, 20px navigation,
24px prominent feedback. Stroke 1.5–2px consistently; decorative icons hidden from
assistive tech, icon-only buttons have explicit names.

Layout: maximum content width 1600px, sidebar 224px, desktop gutter 32px, laptop
24px, mobile 16px. Twelve conceptual columns desktop; detail source 5 / current
fields 7, with a bounded evidence/validation section. Future investigation three
regions: responsibilities, findings, recommendation; collapse below 1200px.

| Breakpoint | Proposed behavior |
|---|---|
| ≥1440px | Full sidebar, source/current columns, three-region AI concept where space allows |
| 1024–1439px | Sidebar or compact rail, two main content columns if readable; AI secondary region wraps |
| 768–1023px | Compact navigation, single review column, blocker summary before source |
| <768px | Labeled navigation drawer/links, 16px gutters, stacked fields, primary facts/actions visible |

Break at content pressure rather than device branding. Preserve `min-width:0` on
grid children and positioned, contained table-scroll regions. Never hide body
overflow to disguise clipped content. At 390px surface invoice identity, amount,
status and review action without horizontal page scrolling. Data tables may scroll
internally with visible instruction and keyboard access.

## Component contracts

The following is a proposed reusable inventory, not a claim these components exist.
Keep native HTML controls when sufficient. Existing APIs remain the source of truth.

| Component | Structure and states | Interaction / accessibility |
|---|---|---|
| Button | Primary, secondary, tertiary, destructive; default/hover/focus/pending/disabled | One primary next step per decision group; pending text with busy state; explain unavailable financial action nearby |
| Field / input | Label, control, hint, error; text/decimal/read-only | Stable id, `aria-describedby`, `aria-invalid`; preserve strings; no placeholder-only labels |
| Select | Native select, visible label, selected value | Native keyboard support; custom combobox only if scale/search requires it |
| Date field | ISO-compatible input with visible format; nullable value | No invented dates, timezone-free invoice dates; type=date only after pinned framework/browser verification |
| Search | Label, text query, clear control, result count | Retain existing debounce; announce completed results, cancel stale requests |
| Filter group | Status and exception type with visible labels, reset | Preserve server semantics; expose selected filters on return; no unsupported backend filters |
| Data table | Caption/label, scoped headers, tabular amounts, contextual action | Keyboard-named scroll region; unique review link; loading/empty/error distinct; no color-only meaning |
| Pagination | Total, page, Previous/Next disabled boundaries | Preserve server page size 20; do not imply export is page-limited |
| Tabs | Review / Original / Activity | Associated panels, ids, roving tab index, Left/Right/Home/End; or use ordinary links if implementing navigation instead |
| Card | Header, count/fact, short explanation, optional real destination | No nested conflicting links; KPI is a count, not an invented trend |
| Status | Text, optional icon, semantic color | Separate invoice state, validation outcome, human decision and future run applicability |
| Tooltip | Supplemental brief explanation | Focus + hover, Escape, persist while hovered; never the only blocker explanation |
| Dialog | Heading, summary, reason, confirm/cancel | Focus entry/trap/return, Escape, labelled modal, no background interaction; avoid finalizing by accidental Enter |
| Drawer | Secondary source or upload form | Modal semantics only if modal; preserve mobile focus and close control; don't hide critical blocker text |
| Toast / notice | Success/info/error with optional real link | Polite status for progress/success, alert for actionable failure; persistent failure near task; no error-only disappearing toast |
| Skeleton | Layout placeholder without fabricated data | Parent `aria-busy`, a single loading status; no noisy repeated live announcements; reduced motion |
| Empty state | Distinguish no records, filtered zero, public restriction | Contextual next action; public mode never tells visitor to upload |
| Error state | Human explanation, safe retry, details disclosure | Preserve structured code in details; no raw response dump; re-fetch on 409 before another action |
| Activity timeline | Icon, event title, actor, timestamp, sentence, transition/diff, optional notes | Semantic ordered list; every stored event available; no inferred actor or decision |
| Evidence card | Source/version, escaped excerpt, support/conflict/missing label | Links resolve authorized sources; no raw HTML, inferred page citation or confidence claim |
| Monetary summary | Currency, subtotal, explicit tax/rate, total, null state | String precision; never sum currencies; no auto-correct action from expected arithmetic |
| Financial comparison | Expected / observed / difference / source | Exact typed values; derived difference must use decimal-safe computation; mobile stacks with labels retained |
| Technical details | Native collapsed `details`, complete payload, colored code, Copy and selection fallback | JSON always escaped, selectable, scrollable; announce copy failure/success; original values intact |
| Field diff | Field / before / after, revision, actor, reason | Source stored audit diff; no inferred modification; null shown as missing, not zero |

## Consolidation within this repository

Existing `desk.tsx` already owns Heading/Badge/Notice/Pager; preserve those contracts
until consumers are migrated. `InvoiceTable` is already shared between overview,
list and queue. Ledger/supplier tables, action rows and details repeat styling.
`invoice-detail.tsx` mixes fetching, draft mutation, review gating and all view
presentations; split pure display adapters from orchestration incrementally.

Proposed organization after approval:

```text
frontend/src/styles/tokens.css                 # semantic foundations
frontend/src/components/ui/                   # button, field, notice, tabs, table, dialog
frontend/src/components/invoices/             # summary, checks, source, revision actions
frontend/src/components/activity/             # event sentence, diff, technical disclosure
frontend/src/lib/presentation/                # neutral rule labels, event adapters, money strings
frontend/src/components/investigations/       # future only, after real Phase 2 contract
```

These paths are proposals, not links to implemented files. Keep the existing desk
provider responsible for auth/mode, query route and statically exported pages.
Presentation functions consume existing types and never decide financial authority.
Unknown events/rules retain full data and use safe fallback names. Do not merge a
business invoice status and future investigation status into one badge enum.

No additional frontend libraries are recommended for the first redesign milestone.
Native details/selects and existing React suffice. Accessible dialogs need careful
focus handling; an audited primitive dependency could reduce that work but adds
bundle/version/maintenance cost. Propose and justify it separately if native dialog
behavior proves insufficient. Use a tiny safe JSON tokenizer, not model-generated
HTML or a large editor. Icon assets can be a small reviewed local SVG set.

## Accessibility acceptance

Target [WCAG 2.2 AA](https://www.w3.org/WAI/WCAG22/quickref/), verified criterion by
criterion, not claimed from a palette. Normal text ≥4.5:1; large text ≥3:1; necessary
non-text identifying boundaries/states ≥3:1. Focus ring 3px, 3px offset, never clipped
or obscured. Keep 44px mobile targets as product standard; WCAG 2.5.8 minimum is
24px with defined exceptions. Support keyboard, 200% zoom, reflow checks at 320 CSS
px with table exception review, reduced motion and semantic announcements. Test
screen-reader labels and focus restoration separately from Playwright visibility.

Calculated B light pairs: main/white **14.57:1**, muted/white **6.07:1**,
white/primary **7.63:1**, success pair **6.81:1**, warning **6.61:1**, error
**5.91:1**, information **6.16:1**. These mathematical pairs do not validate every
hover, disabled, nested or dark-mode state. Proposed dark mappings are in
[theme comparison](THEME_COMPARISON.md); no dark implementation is included.

## Financial meaning and learning

Progressive disclosure means presenting a readable decision summary while retaining
the full evidence one level deeper. It must not conceal a blocker. A presentation
adapter translates `INVALID_DATE_RANGE` to “Invoice date range”; it does not change
the deterministic result. Semantic tokens let one component express “blocked”
consistently across themes. Revision-specific UI makes time visible: original facts,
current saved data and an approved historical payload are separate things.

Owner exercise: open the B original-extraction concept, expand JSON and compare
`total` with the structured summary. Then read the existing corrected invoice's
history in the private app: identify original 2500.00, saved 2300.00, the review
revision and subsequent ledger action without changing any record. The future
timeline should make that reconstruction possible without opening JSON.
