# Three visual directions

These are original proposals, not copies or claims to have inspected the current
interfaces of other products. Linear/Vercel suggest disciplined hierarchy;
Stripe suggests legible financial data; Ramp/Mercury suggest a finance-first
worklist; Retool suggests operational density; Notion suggests evidence reading.
No competitor screenshot, logo, scraped asset or external font is used.

Open the [local comparison gallery](design-preview/index.html), or directly:
[Theme A](design-preview/theme-a.html), [Theme B](design-preview/theme-b.html),
[Theme C](design-preview/theme-c.html). Each includes Overview, Invoice list,
Invoice detail, Exception investigation, Activity timeline, Structured original
extraction and Future AI workspace. Browser screenshots belong only in ignored
`storage/ui-audit/concepts/`; the HTML is the reviewable visual reference.

## Exact light palettes

| Token / role | A: Modern Enterprise | B: Financial Intelligence | C: Evidence Workspace |
|---|---|---|---|
| Primary action | `#1D4ED8` | `#155E51` | `#5B21B6` |
| Secondary / deep ink | `#0F172A` | `#112F2A` | `#26213B` |
| Accent | `#0F766E` | `#795B25` | `#0E7490` |
| Canvas | `#F6F8FC` | `#F5F6F3` | `#F7F6FB` |
| Surface | `#FFFFFF` | `#FFFFFF` | `#FFFFFF` |
| Secondary surface | `#F1F5F9` | `#EFF3EF` | `#F1EFF8` |
| Sidebar | `#0F172A` | `#112F2A` | `#26213B` |
| Sidebar text | `#E2E8F0` | `#DCEAE4` | `#ECE7F7` |
| Border, decorative | `#CBD5E1` | `#D5DED8` | `#D8D3E7` |
| Primary text | `#0F172A` | `#172D27` | `#211B35` |
| Secondary text | `#475569` | `#52675E` | `#625775` |
| Success / surface | `#166534` / `#F0FDF4` | Same | Same |
| Warning / surface | `#854D0E` / `#FFFBEB` | Same | Same |
| Error / surface | `#B91C1C` / `#FEF2F2` | Same | Same |
| Information / surface | `#1D4ED8` / `#EFF6FF` | Same | Same |
| Focus ring | `#1D4ED8` | `#1D4ED8` | `#1D4ED8` |
| Input boundary, proposed production token | `#64748B` | `#64748B` | `#64748B` |

Semantic colors remain stable across themes: changing the brand should never
change what a blocker means. Decorative pale card borders are not sufficient as
the only identifying boundary of a required input; use the stronger input token
and visible labels in production. Preview light borders are a concept limitation.

## Theme A: Modern Enterprise

Neutral slate with blue actions. Segoe UI/Arial throughout; optional self-hosted
Inter later, with licensing review and system fallback. H1 30/36, H2 18/26, body
14/21, labels 13/18, metadata 12/18; weights 400/600/700. Four-pixel spacing base,
16–24px panel padding, 6px radius, no ambient shadows. Dense rows use 12px vertical
padding without making text smaller. Navigation uses clear slate active surfaces;
dashboard is an operational worklist with compact counts. Forms use flat labeled
fields; primary blue, neutral secondary, text tertiary, red destructive actions.
One consistent 16/20/24px line-icon family with text labels.

Advantages: familiar, easy to scan, minimal design maintenance; data tables feel
natural. Disadvantages: less distinctive among enterprise tools; blue/white alone
will not fix the technical information architecture. Good choice when brand
neutrality outweighs product character.

## Theme B: Financial Intelligence — recommended

Deep teal, ink, warm-neutral surfaces and restrained brass used for section cues,
not warnings. Segoe UI/Arial for operational content; Georgia only for a sparse
page title in the concept, never money or table data. Optional self-hosted Source
Sans 3 is an alternative after actual readability evaluation. H1 32/38, H2 17/26,
body/table 14/21, labels 13/18, metadata 12/18; weights 400/600/650/700 where the
chosen font supplies them. Use genuine available font weights rather than relying
on synthetic 650 in production. Four-pixel spacing base, 20–24px panel padding,
8px radius; shadow `0 2px 6px #112F2A08` only for separation.

Sidebar has clear selected state, restrained branding and labeled destinations.
Dashboard prioritizes held work and exact currency values. Tables keep tabular
numerals, calm separators and clear action links. Forms distinguish source facts,
current edits and human decisions. Teal primary action is reserved for the current
next step. Semantic red/amber belongs to exceptions. Same icon sizing/family as A.

Advantages: retains the product's existing visual continuity, feels appropriate
for accountable financial decisions, supports evidence without looking like a chat
tool. Disadvantages: needs restraint to avoid muddy green-on-green status color;
serif headings can feel editorial and must remain rare. Remove the serif if operator
testing favors a fully sans-serif interface. Never use brass for low-contrast body
copy or to imply risk by itself.

## Theme C: Evidence Workspace

Graphite sidebar, violet navigation/actions and cyan source accents. Segoe UI/Arial
for both reading and operations; optional self-hosted IBM Plex Sans later. H1 30/38,
H2 17/26, body 14/22, labels 13/18, metadata 12/18; weights 400/600/700. Four-pixel
spacing base, 18–24px grouped panel padding, 10px radius, shadow
`0 2px 8px #26213B09`. Panels have tinted section headers and modular evidence
grouping. Financial tables remain neutral; violet is not a success/risk signal.
Forms use the same exact-value and primary/secondary action rules as A/B.

Advantages: supports reading findings, sources and unresolved questions in adjacent
panels; future agent responsibilities fit naturally. Disadvantages: may overemphasize
unimplemented AI, more competing visual cues, greater density-management burden.
Do not surface it as a working AI product before implementation and evaluation.

## Light, dark and accessibility

All concepts ship **light only**. Dark mode is a proposed separate mapping, not
simple CSS inversion or an implemented toggle:

| Dark token | A proposal | B proposal | C proposal |
|---|---|---|---|
| Canvas | `#0B1220` | `#101C18` | `#171321` |
| Surface | `#162033` | `#1B2A23` | `#241E32` |
| Raised / sidebar | `#1E293B` | `#24382D` | `#302842` |
| Border | `#64748B` | `#718478` | `#82738F` |
| Main / muted text | `#F1F5F9` / `#CBD5E1` | `#EDF5EE` / `#B9CBBE` | `#F3EEFA` / `#C7BCD9` |
| Primary fill / on-primary text | `#93C5FD` / `#0F172A` | `#9FD4B4` / `#112F2A` | `#C4B5FD` / `#26213B` |
| Accent | `#5EEAD4` | `#E2C78E` | `#67E8F9` |

Shared proposed dark semantics: success `#BBF7D0` on `#143522`, warning `#FDE68A`
on `#3A2B12`, error `#FECACA` on `#3C1919`, information `#BFDBFE` on `#162C4B`;
focus `#93C5FD`. Validate every real composition before shipping. PDF source paper
should remain readable without recoloring original documents.

All light themes require WCAG 2.2 AA contrast, keyboard operation, text alongside
status color, visible focus and motion reduction. Readability, table precision and
action clarity take priority over decorative differences. See the
[design system](DESIGN_SYSTEM.md) for measured B contrasts and acceptance rules,
grounded in [W3C guidance](https://www.w3.org/WAI/WCAG22/quickref/).

## Selection rationale

Qualitative comparison against this product, not a numerical user study:

| Criterion | A | B | C |
|---|---|---|---|
| Routine finance scanning | Strong | Strong | Good; more panel emphasis |
| Continuity with current app | Moderate | Strongest | Weakest |
| Distinct commercial identity | Familiar | Distinct but restrained | Distinct, AI-forward |
| Evidence reading | Good | Strong | Strongest |
| Avoid overstating AI maturity | Strong | Strong | Requires prominent caveats |
| Implementation effort | Low | Low–moderate | Moderate |

Choose **B** because the product sells controlled financial decisions, and the
existing design already establishes a credible forest palette. Its measurable
contrast improvements and clearer evidence hierarchy matter more than changing
brand personality. Borrow C's modular investigation layout only after Phase 2
contracts exist. The owner should compare the same wrong-total, original-extraction
and timeline screens under all three themes before approving implementation.
