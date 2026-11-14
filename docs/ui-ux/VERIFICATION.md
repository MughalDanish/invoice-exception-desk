# Audit and concept verification

Scope: local, non-mutating inspection on 14 November 2026. No deployment, external
localhost fetch, frontend package installation or backend migration. User explicitly
requested audit/concepts and required approval before application changes.

## Executed commands

From the independent `invoice-exception-desk` root:

| Command | Actual result |
|---|---|
| `node docs/ui-ux/tools/audit.mjs` | Exit 0. Final pass: 196 unique application captures, both modes, 4 viewports; zero page-overflow measurements, zero uncaught page errors, zero mutation requests attempted; statistics/ledger/supplier reads identical before/after |
| `node docs/ui-ux/tools/probe.mjs` | Exit 0. Two supplemental screenshots, actual keyboard behavior, browser-only unsaved draft, console/page errors checked |
| `.venv/Scripts/python.exe docs/ui-ux/tools/generate_previews.py` | Exit 0. Three independent HTML concept entries and data.js generated solely from committed public synthetic projection |
| `node docs/ui-ux/tools/verify-previews.mjs` | Exit 0 after mobile grid correction. 84 concept captures = 3 themes × 7 screens × 4 viewports; 9 functional checks; zero page errors or external HTTP requests |
| `node --check` for concept.js, audit.mjs, probe.mjs and verify-previews.mjs | Exit 0 for each |
| `git diff --check` | Exit 0; tracked application files unchanged |

The first concept verification correctly failed on Theme A mobile overview grid
overflow. Fixed the standalone shell's minimum track size with
`minmax(0,1fr)` and `min-width:0` on sidebar. The next full 84-capture run passed.
No production layout was modified. Two ad hoc measurement-printing commands hit
Windows text-encoding errors; explicit UTF-8 file reading and ASCII JSON output
resolved analysis. These were tooling issues, not application failures.

Capture totals are **196 application + 2 supplemental + 84 concept = 282 final
referenced captures**. Earlier captures remain in ignored storage and are not
additional independent cases. No historical test result is counted in these totals.

## Safe supplemental findings

- Ready clean invoice: Save disabled, Revalidate enabled, Approve enabled, Reject
  disabled until a reason, Post enabled. Main action heights measured 39px.
- Changed Total to `1150.01` in browser memory and entered a draft note. Save became
  enabled; Revalidate, Approve, Reject and Post disabled. No request submitted;
  navigating away discarded the draft. This is **not a saved correction**.
- Switching Review → Audit → Review retained the unsaved draft within the same
  mounted invoice. No approval or success message fabricated.
- Focusing Review and pressing ArrowRight left focus and selection on Review.
  Click navigation works. Confirms absent ARIA-tab arrow behavior identified in
  source, beyond the DOM's missing panel association and roving tab index.
- Public post action absent. Actual browser console errors: **0**; page errors: **0**
  in the supplemental private/public route sequence.
- Five failed-request notifications were `net::ERR_ABORTED`: three blob document
  requests and two API reads during route/filter changes. No console error or
  demonstrated API outage. Cancellation is distinct from an HTTP failure.

Main capture runs recorded uncaught page errors; the supplementary probe added
console and failed-request observation. Do not interpret these targeted checks as
an exhaustive network-performance or security test.

## Concept behavior checks

Three checks per theme:

1. Invoice search filters actual fixture rows and displays a meaningful filtered
   empty state. Native status selector also operates on the local dataset.
2. Source JSON is collapsed, syntax spans exist, parsed displayed payload equals
   the fixture's preserved original exactly, and manual selection includes the
   original `2500.00` decimal string. Automatic clipboard granting is browser
   dependent and is not claimed as verified on all file:// browsers.
3. Every financial action in the detail concept is disabled.

All 84 capture combinations assert no page overflow. The concept browser made no
HTTP(S) requests, proving independence from APIs/external assets during these
views. Data comes from `fixtures/public-demo.json`, including counts 15/9/4/1.
Wrong-total expected/observed comparison uses that known fixture, not a live
computation or a newly generated finding. Fictional correction comparison and
future AI content are prominently labelled.

## Reproduction and evidence handling

Use the installed frontend Playwright and local Chromium; `.env` is consumed in
memory by audit/probe only. Do not run writable acceptance scenarios against the
owner's existing database. Main audit reads both current modes; it does not start,
rebuild, expose or reset containers. A fresh clone needs the existing private/public
stacks running on their configured ports before application capture.

Evidence directories:

```text
storage/ui-audit/evidence.json             # Main computed styles/geometry and checks
storage/ui-audit/*.png                     # 196 final main capture names + supplements
storage/ui-audit/private-ledger.csv        # Existing posted ledger GET export, ignored
storage/ui-audit/probe.json                # Keyboard, console, draft observations
storage/ui-audit/concepts/evidence.json    # Standalone preview measurements
storage/ui-audit/concepts/*.png            # 84 preview images
```

The entire storage tree is already ignored. Capture login inputs and operator
header are masked. No passwords, Basic tokens, cookies, request headers or HAR
files are saved. Never promote private CSV or storage captures into public assets
without a separate content review. The committed previews use only the existing
public synthetic read model, not private audit exports or credentials.

## Deliberate verification limits

- No mutation success/pending result, real upload, approval, rejection, supplier
  registration, retry or posting was invoked. Existing history was inspected.
  Loading and 503 screenshots are browser-intercepted examples, not live outages.
- Public held/failure cases cover states absent in private records; that does not
  verify a private financial submit interaction in this task.
- PDF iframe appears gray headlessly; protected preview element and download path
  exist. No claim of successful interactive PDF rendering or PDF accessibility.
- No screen-reader run, formal WCAG audit, automated accessibility scanner, zoom
  or physical-device touch test. Contrast ratios are calculated from identified
  CSS pairs; font-size preference alone is not a WCAG failure.
- No actual AI execution, retrieval, agent trace, token usage, latency/cost report,
  multi-user/admin auth, supplier edit, dark mode or financial confirmation dialog
  exists in these deliverables. Future layouts are illustrative.
- Full backend regression, writable acceptance tests and Next.js production builds
  were not rerun for documentation/static-only additions. They would not verify
  the new HTML concepts; the dedicated browser checks do. Actual production
  redesign must run the full regressions in the roadmap.
- No external reference product was scraped. The W3C quick reference was retrieved
  through the Firecrawl skill for standards only; localhost was never sent there.
- No Git commit or push is required by this audit request. New files are confined
  to `docs/ui-ux/` and screenshots to ignored storage. Existing application remains
  at the same baseline for a clean before/after comparison.
