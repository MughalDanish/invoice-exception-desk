# Day 14: investigation UI maintenance guide

The investigation tab adds an advisory workspace to the existing invoice review.
It does not call invoice correction, supplier approval, validation, approval or
posting actions. Those controls remain in their existing review components.

## Files and responsibilities

- `frontend/src/components/invoice-detail.tsx`: adds the investigation tab and
  passes the authoritative invoice plus unsaved-edit state.
- `frontend/src/features/investigations/types.ts`: small frontend contracts for
  runs, structured reports, citations and event pages. Backend remains authoritative.
- `api.ts`: typed endpoint functions using the existing cookie/CSRF/refresh client.
- `presentation.ts`: pure helpers for active-state polling, current-report gating,
  scoped evidence URLs, action labels and unresolved evidence.
- `queries.ts`: query keys, request cancellation, conditional polling, and
  non-optimistic start/cancel/retry mutations with targeted cache invalidation.
- `investigation-panel.tsx`: private/public boundary, paged run selector, run
  controls, report, on-demand source viewer and paged event timeline.
- `frontend/src/app/globals.css`: horizontally scrollable review tabs when labels
  exceed a narrow pane; two-column mobile tabs keep every label visible. Existing
  Theme B styling and shadcn controls are reused.
- `frontend/unit-tests/investigations.spec.ts`: scope, stale, polling and safe
  recommendation fallback tests without browser/database requirements.
- `frontend/tests/investigations.spec.ts`: isolated real API queue/cancel flow,
  reload persistence, financial invariance and adversarial rendering fixture.
- `frontend/public-tests/public.spec.ts`: verifies no investigation requests or
  controls are exposed in public mode.
- `frontend/playwright.visual.config.ts` and `frontend/visual-tests/investigation.spec.ts`:
  presentation-only fixtures without an API/database/model process; checks exact
  financial strings, evidence display, all tab bounds and four viewport widths.

## Component and data flow

`InvoiceDetail → InvestigationPanel → PrivateInvestigations → RunDetails → Report`
and `InvestigationTimeline`. `Report → Evidence → EvidenceBody` fetches a source
only after the user opens it.

The public boundary returns before mounting query-bearing children. This matters:
merely hiding a button does not prevent hooks from making unauthorized requests.
Private hooks use the global QueryClient and centralized `request` function;
passwords and tokens never enter feature state.

The run list provides summary metadata, not the full report. Selecting a run fetches
its detail separately. Offset pagination is server-backed. QUEUED/RUNNING runs
poll every 2.5 seconds; terminal runs stop polling. The detail key also includes
the current invoice revision so a correction causes applicability to be checked.
Timeline queries include activity state so transition to terminal status fetches
the final events. No `useEffect` fetching or duplicate server-state copies exist.

Start sends expected revision and a fresh idempotency key. It is disabled while
edits are unsaved, validation is outdated, an active run is present, or invoice
status is not NEEDS_REVIEW. Server checks remain mandatory because a browser can
be stale or modified. Mutations have no automatic retries and show success only
after the server responds. Cancel requires confirmation. Retry explains that
ownership, remaining attempts and budget are enforced by the backend.

## Safety patterns

React text rendering escapes findings, recommendations and source excerpts; the
UI never parses model Markdown or uses `dangerouslySetInnerHTML`. Model/source
URLs are not trusted navigation. `safeEvidencePath` permits only the exact current
invoice's UUID-scoped versioned evidence endpoint, strips the API prefix for the
existing authenticated client, and rejects schemes, external origins, query
strings, fragments, traversal and cross-invoice paths.

Report rendering requires COMPLETED, applicable and an exact source revision
match. A stale report is withheld from the normal findings view; complete run
metadata remains available via the existing technical JSON inspector. The server
also suppresses stale report publication. Provenance is not proof of authenticity.
Mock mode is explicitly labeled as deterministic offline development output.

## Modify components independently

Change labels and status policy in `presentation.ts` and add unit cases first.
Change report layout in `Report` without modifying request/authentication logic.
Change polling/caching in `queries.ts`; leave terminal-state detection centralized.
Add report fields to `types.ts` only when the backend contract supplies them.
Keep financial operations outside this feature. Source content belongs in escaped
text nodes, never executable links, HTML or a model-provided embed.

## Verification commands

Run from `frontend`:

```powershell
npm.cmd run typecheck
npm.cmd run test:unit
npm.cmd run build
npm.cmd run test:e2e
npm.cmd exec playwright test -- --config playwright.public.config.ts
npm.cmd exec playwright test -- --config playwright.visual.config.ts
```

Browser scripts provision synthetic data in isolated PostgreSQL schemas. Private
and public runs use separate API/frontend ports; do not reuse production/demo
credentials or change live data to make tests pass. The source/XSS report fixture
is an explicit simulated UI payload; it is not evidence of a live Gemini call.
The visual fixture suite also simulates authentication metadata and all API
responses; it proves rendering behavior, not authentication or backend operation.
See the progress report for actual results and limitations.
