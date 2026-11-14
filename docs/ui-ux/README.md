# UI/UX audit and design review

Start with the [visual theme gallery](design-preview/index.html). Open it directly
in a local browser; no server, installation or credentials are needed. Choose a
theme and use its seven screen links. The concepts do not call the API or change
records. Future AI content is explicitly hypothetical.

| Deliverable | What it contains |
|---|---|
| [UI/UX audit](UI_UX_AUDIT.md) | Verified problems, 15 rated areas, screenshot references, responsive/accessibility findings and inspection limits |
| [Theme comparison](THEME_COMPARISON.md) | Three exact palettes, visual styles, tradeoffs, dark proposals and recommended B direction |
| [Design system](DESIGN_SYSTEM.md) | Semantic tokens, type/spacing/layout, full reusable component inventory and architecture proposal |
| [Information architecture](INFORMATION_ARCHITECTURE.md) | Navigation, current journeys, evidence disclosure and future advisory workspace |
| [Redesign roadmap](UI_REDESIGN_ROADMAP.md) | Priorities, dependencies, acceptance criteria, regression strategy and approval boundary |
| [Verification](VERIFICATION.md) | Actual commands, capture counts, safe keyboard/draft probes and limitations |

Recommended direction: **B / Financial Intelligence**. First proposed production
package: **R1 / readable financial evidence**. The current application and financial
workflows are untouched. No Phase 2 feature or public deployment was performed.
Explicit owner approval is required before implementing the redesign.

Screenshots and raw measurements are intentionally ignored under
`storage/ui-audit/`, not committed in this directory. They are local evidence;
links will not work in a fresh checkout until regenerated. The standalone HTML
concepts are portable and contain only the existing public synthetic dataset.

Preview limitations: static concepts with disabled financial actions, light mode
only, source-text excerpt rather than a PDF imitation, native controls, no real
dialog, no production-perfect mobile card table. Clipboard may require permission
or a secure context; select-and-copy fallback works without it. Concepts compare
design directions and do not claim all proposed components are implemented.
