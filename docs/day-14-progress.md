# Day 14 UI progress

19 November 2026. Implemented in parallel with the separately owned Day 13 live
provider work. No remote push or financial workflow changes. Local container
activation is coordinated separately in the combined Day 13/14 report.

## Implemented

- Invoice detail investigation tab with current-validation/unsaved-edit gating.
- Server-backed run pagination, persisted selection discovery after reload,
  active-only polling, progress, errors, cancel confirmation and retry controls.
- Distinct scripted-mock/live-Gemini labels and explicit advisory-only guidance.
- Current source revision/applicability gates; stale findings are withheld.
- Structured findings, evidence references, recommendation rationale, unresolved
  uncertainties, limitations and model metadata when supplied by the server.
- Authenticated on-demand versioned evidence viewing with strict invoice-scoped
  URL allowlist; all source/model text is escaped by React.
- Paginated metadata timeline and preserved technical payload inspector/copy.
- Public read-only boundary mounts no investigation API hooks or mutation controls.
- Existing Theme B, shadcn controls, TanStack Query and centralized cookie auth
  reused. No added frontend dependency or competing state system.

## Verification

Initial typecheck passed. Frontend unit suite: **42 passed**, exit 0 (10.8s),
including four new investigation presentation tests. Production build passed,
exit 0, with eight static pages generated. Targeted ESLint passed, exit 0.
Final unit suite after adding safe telemetry: **43 passed**, exit 0 (10.9s).
Final typecheck and targeted ESLint passed, exit 0. Final production build after
adding the structured assertion table passed, exit 0: eight static pages,
13.0s compilation and 24.2s TypeScript stage. `git diff --check` passed.

First private browser attempt: **3 failed**, including both pre-existing tests,
while PostgreSQL returned `FATAL: the database system is in recovery mode` during
upload/authentication and cleanup. This attempt does not verify the new controls.
PostgreSQL subsequently reported accepting connections. Shared-DB browser reruns
are serialized with backend tests to reduce contention. Windows test-server
teardown also remained pending after the assertions. Public first start executed
no assertions because the stale private Next server retained its development
lock; only verified test-server processes were stopped. Clean public rerun:
**3 passed**, actual exit 0 (5.8m including Windows teardown), including no
investigation requests/controls in public mode.

Second private attempt: **3 failed**, exit 1, during simultaneous Docker builds
and backend/live verification. Existing workflow test reached its unchanged
120-second timeout, login remained pending beyond the unchanged 15-second
assertion deadline, and the new investigation test timed out awaiting upload
dialog completion before reaching investigation controls. Its captured page
subsequently showed the completed upload notification. The coordinator confirmed
severe host contention and paused browser execution; existing timeouts were not
inflated. Only verified private test process trees were stopped. A quiet-window
private rerun was scheduled. No timeout settings were changed.

Quiet-window private rerun: **3 passed**, actual exit 0 (6.7m including Windows
test-server teardown). Existing financial workflow passed in 1.6m; existing
authentication/mobile test passed in 36.5s; new investigation test passed in
57.3s. The new test verified real API queue/reload/cancel, exact unchanged invoice
detail before/after, mock/live labels, explicit simulated structured report,
blocked unsafe evidence URL, authenticated source reading, inert HTML-like text,
and page bounds at 1440/1024/768/390px. A Windows asyncio connection-reset warning
was logged after browser connection closure without failing assertions.

Visual inspection identified a partly clipped fourth mobile tab. A minimal
mobile-only two-column grid now keeps all four tabs visible. Screenshot capture
normalizes scroll and clears focus to avoid full-page sticky-header artifacts.
The first focused real-API rerun failed before reaching the UI because its cold
login remained pending beyond the existing 15-second assertion deadline (actual
exit 1). No timeout was extended. The previous complete three-test pass remains
valid for the API workflows.

Presentation-only verification was separated from authentication/database latency:
`playwright.visual.config.ts` starts only Next on port 3003; all API responses are
explicit intercepted synthetic fixtures. The first presentation run found the
same clipping at a narrow laptop split pane (exit 1). A small container query now
uses two-column tabs whenever the review pane is narrow, preserving one row in
wide panes. The corrected presentation run passed its assertion test in 18.5s,
including all four widths, exact Decimal/currency rendering and source viewing.
Final presentation suite: **1 passed**, actual exit 0 (3.6m including Windows
test-server teardown). Only its verified Next test process was stopped afterward.

Final normalized screenshots were captured and visually inspected at desktop,
laptop and mobile widths. They are **synthetic presentation fixtures, not genuine
Gemini output**:

- `storage/day-14-report-fixture-1440.png`
- `storage/day-14-report-fixture-1024.png`
- `storage/day-14-report-fixture-768.png`
- `storage/day-14-report-fixture-390.png`

The screenshots show blank embedded PDF rendering in headless Chromium; the
original fixture file was still served. The Next development-tools control may
appear in captures and is absent from production builds. Sticky-header/focus
capture artifacts were resolved by scrolling to the top and clearing focus.

## Limitations

The browser cannot predict requester ownership or remaining worker budget because
the run view does not expose those capabilities. Controls defer to authoritative
server denial and display the error. Polling is foreground-only and stops at
terminal status. Manual refresh can recheck applicability after external evidence
changes. Supporting sources are read on demand; they are not source-upload or
supplier-approval controls. No claims about live model quality follow from UI
tests. Broader backend security/live smoke results belong to the Day 13 handoff.

Learning guide: [learning-day-14.md](learning-day-14.md).
