# Day 4 — Dashboard and automation

Implemented locally on `feature/invoice-exception-desk`.

## Follow-up: login through the numeric loopback address

Opening `http://127.0.0.1:3000` initially failed because CORS allowed only
`http://localhost:3000`. API logs showed rejected OPTIONS requests while health
remained successful. Both explicit local origins are now allowed by default;
Compose also honors the configured `CORS_ORIGINS` instead of hardcoding one.
The local ignored environment was updated and the backend recreated. Both CORS
regression cases passed, and real Chromium login/data/detail/mobile checks passed
through both addresses. Untrusted origins remain rejected.

## Delivered

- `frontend/src/`: Next.js / TypeScript / Tailwind dashboard with authenticated
  overview, invoice search/pagination/status and issue filters, upload + extraction,
  exception queue, protected source preview/download, editable fields/line items,
  current rule explanations, revision-aware correction/revalidation/review/posting,
  immutable terminal records, audit history, supplier registration and ledger CSV.
- Static export with `/invoices/detail/?id=UUID`, supporting future static hosting
  without generating dynamic invoice paths at build time. Credentials stay in tab
  memory; finance values stay decimal strings. Backend controls every write.
- `backend/app/modules/invoices/integration.py`, integration auth, ingestion changes
  and migration `0004_integration_delivery`: separate integration-key upload and
  processing, durable hashed delivery receipts, replay/conflict handling and
  cross-source file deduplication. No integration approval/posting permissions.
- Invoice list current-batch issue filtering and batched issue summaries; overview
  duplicate count, recent activity and per-currency totals.
- `n8n/workflows/invoice-intake.json`: one importable, inactive workflow with protected
  webhook intake, single attachment guard, integration-authenticated multipart
  request, bounded retries, safe result, sanitized failure branch, and disabled
  optional Gmail/Telegram nodes. `n8n/build_workflow.py` regenerates the artifact.
- Optional Compose profiles: `dashboard` serves the static export through nginx on
  localhost:3000; `automation` runs pinned n8n 2.46.6 on localhost:5678.
- Browser acceptance tests with isolated PostgreSQL schema, explicit Windows cleanup,
  a read-only built-dashboard check, n8n CLI replay smoke, and setup documentation.

## Verification

- Container/PostgreSQL pytest: **142 passed**, one existing Starlette/httpx
  deprecation warning. Includes wrong/missing integration auth, separation from
  operator auth, durable replay, changed-byte conflict, concurrent identical
  delivery, cross-source dedupe, invalid attachments/keys, failed extraction without
  email-driven retry, current issue filters and dashboard statistics. Existing
  migration round-trip, concurrency, rollback, review and posting tests still pass.
- Host Next.js production build and TypeScript check passed. Linux multi-stage
  frontend Docker build also passed and generated all six application routes.
- Final combined Playwright acceptance run: **2 passed** in 1.4 minutes, covering
  real API clean posting, wrong-total correction/revalidation/approval/posting,
  duplicate blocking/rejection, immutable fields, audit diff, CSV download,
  supplier registration, invalid login, populated mobile containment, issue filters,
  refresh and sign-out. The Windows test API logged one non-failing socket-reset
  callback during an aborted connection; assertions and database cleanup passed.
- `node scripts/check_dashboard.mjs`: passed against the actual built dashboard at
  localhost:3000, including login/data/detail navigation and populated mobile
  layout, with no JavaScript errors or invoice writes. Synthetic screenshots were
  inspected and remain in ignored `storage/previews/`.
- `docker compose exec -T backend python -m app.smoke`: passed again against the
  existing demo data, returning the original clean/corrected ledger IDs, blocked
  duplicate, verified correction audit/source download, and two exported CSV rows.
- n8n 2.46.6 imported the versioned workflow successfully. The real exported
  guard/HTTP/result nodes ran against FastAPI using a synthetic clean-004 fixture.
  `scripts/n8n_smoke.py` executed the same delivery twice and verified the same
  backend invoice ID, without posting. It imports the backend credential over
  stdin into encrypted n8n storage and leaves a clearly named CLI test workflow.
- Ruff check/format, pip dependency consistency and Git whitespace checks passed.

The initial browser runs exposed ambiguous test locators and a real mobile
overflow caused by an absolutely positioned hidden table heading. Distinct
evidence labels and a positioned horizontal scroll container resolved those.
The desktop acceptance scenario and independent mobile scenario passed. A later
combined run during concurrent container building/n8n CLI startup encountered
database availability/timeouts. Final combined checks passed after those tasks
completed; API health returned 200 with the expected migration and mock mode.

## Local use

```powershell
docker compose up -d --build backend
docker compose exec -T backend alembic upgrade head
docker compose exec -T backend python -m app.seed
docker compose --profile dashboard up -d --build frontend
```

Open http://localhost:3000. Sign in using the operator username/password from
the ignored root `.env`. Upload supplied synthetic fixtures. A clean invoice can
be posted explicitly; an exception must be corrected/revalidated/current-revision
approved before posting. Every important action is visible in Audit history.

Frontend host setup/tests: [frontend README](../frontend/README.md).
Automation configuration and test: [n8n README](../n8n/README.md).

## Remaining scope and limits

- Gemini is SDK-tested offline, not live-model verified. Mock mode is fully usable.
- Gmail OAuth, live webhook credential setup and Telegram delivery require owner
  configuration; Gmail/Telegram nodes remain disabled. The successful CLI smoke
  tests internal intake nodes, not those external services.
- No auto-posting, background worker, email-driven extraction-failure retry,
  multi-attachment splitting, Telegram approval, ERP writeback or payments.
- Basic auth and HTTP-only local n8n cookies are local demo configuration.
  Public read-only mode, deployment preparation, benchmark and final portfolio
  artifacts belong to Day 5. Nothing has been publicly deployed.
- GitHub publication remains deferred under the owner's prior authorization to
  continue locally until GitHub access is restored.
