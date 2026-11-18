# Invoice Exception Desk

Catch invoice mistakes before they reach your ledger.

An invoice exception-management demonstration using synthetic invoices.
Days 1–5 implement ingestion, extraction, validation, human review, safe ledger posting,
audit history, CSV export, the dashboard, optional n8n intake and a read-only portfolio mode.

## Stack

- Backend: FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, PostgreSQL 16.
- Frontend: Next.js, TypeScript, Tailwind CSS.
- Extraction: deterministic mock adapter, optional Gemini adapter.
- Automation: optional n8n Gmail ingestion and notifications.

## Current status

Implemented: FastAPI, PostgreSQL models and Alembic migration, private PDF/JPG/PNG
upload (8 MiB), SHA-256 deduplication, authenticated invoice list/detail/download,
audit history, supplier list, an idempotent seed CLI, and 16 synthetic PDFs with
deterministic answer keys. Day 2 adds hash-based mock extraction, an optional Gemini
adapter, strict Pydantic extraction schemas, Decimal rule checks, persisted rule
results, recoverable processing attempts, and business duplicate detection.
Uploads start `RECEIVED`; processing produces `READY_TO_POST`, `NEEDS_REVIEW`,
or `EXTRACTION_FAILED`. Nothing is automatically posted.

Day 3 adds audited corrections, explicit revalidation, revision/payload-bound review,
rejection, transactional posting with fresh validation and database uniqueness,
immutable ledger snapshots, supplier registration, ledger pagination, sanitized CSV,
and per-currency dashboard statistics. Posted and rejected invoices are terminal.

Day 4 adds an authenticated Next.js / TypeScript / Tailwind dashboard, protected
document preview, exception review, supplier registration, ledger and audit screens,
plus a separate integration-key intake endpoint with durable delivery receipts and
an importable n8n workflow. The static export supports future static hosting.

Day 5 adds a fail-closed public synthetic read model, the original 16-fixture
benchmark, public write-denial tests, deployment configurations, screenshots,
silent walkthrough and owner learning notes. PostgreSQL remains authoritative for
the writable workflow; the public process serves only a curated fixture export.

Actual cloud deployment remains pending owner access/authorization. Live Gemini
extraction and Gmail-to-Slack intake were verified locally during Phase 1 follow-up.
Automated regression tests use synthetic fixtures and fake SDK transports; Day 6
does not run live model calls or send notifications.

The Phase 2 documents are preserved in [docs/phase-2](docs/phase-2/AI_UPGRADE_START_HERE.md).
Day 6 adds an advisory-only LangGraph mock investigation with strict typed contracts,
snapshot-bound reports, an additive migration and operator-authenticated API routes.
Day 7 extends it with a validated mock supervisor, sequential financial/supplier
roles and five scoped read-only tools for totals, duplicates, supplier approval and
amount outliers. It describes captured evidence without changing financial records.
Unknown blockers and missing evidence remain explicit limitations.
See [Day 6 learning guide](docs/learning-day-6.md) and
[milestone results](docs/day-6-progress.md). Current results and concepts are in the
[Day 7 report](docs/day-7-progress.md) and [learning guide](docs/learning-day-7.md).
Day 8 adds parallel financial/supplier/document branches with an explicit join,
a versioned append-only supporting-evidence table, scoped bounded capture and a
synthetic PO/receipt/email corpus. The document branch inventories missing evidence;
it does not reconcile text or grant financial authority. See the
[Day 8 report](docs/day-8-progress.md) and [learning guide](docs/learning-day-8.md).
Day 9 requires separate confirmation.

Run the isolated synthetic example (existing local PostgreSQL must be running):

```powershell
.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
.venv/Scripts/python.exe scripts/run_investigation_demo.py
.venv/Scripts/python.exe scripts/run_routing_demo.py
.venv/Scripts/python.exe scripts/run_parallel_demo.py
```

The example creates and removes its own schema and writes only a synthetic report
to ignored `storage/day-6-synthetic-report.json`. No API key or live model is used.
It does not update the running containers. To enable these new routes on your local
backend, build its image and run Alembic before starting the updated backend:

```powershell
docker compose build backend
docker compose run --rm --no-deps backend python -m alembic upgrade head
docker compose up -d --no-build --no-deps backend
```

The routing demo writes four synthetic reports to `storage/day-7-synthetic-reports.json`.
This milestone has no investigation screen, parallel workers, retrieval corpus or durable worker.
Existing invoice controls and n8n intake remain independent of investigations.

## Day 5 results and public preview

- Previous milestone rerun: 143 PostgreSQL tests and 2 browser scenarios passed.
- Day 5 regression: 181 backend tests, 2 operator browser scenarios, and 1 anonymous
  public-demo browser scenario passed. [Detailed report](docs/day-5-progress.md).
- [Phase 1 benchmark](docs/benchmark.md): 16 original submissions; 11 held/deduplicated
  or failed safely, 5 clean posts; no missed holds or false holds in this scripted set.
  Live-model extraction accuracy is **NOT RUN**, not inferred from mock results.
- [Screenshots, silent video and two-minute demo script](docs/demo-script.md),
  [portfolio draft](docs/portfolio.md), [engineering lessons](docs/learning-day-5.md).
- [Deployment preparation and limits](docs/deployment.md): Render Blueprint and
  private-VM HTTPS configuration. Nothing has been deployed publicly.

To run a separate local public-mode preview without credentials or a database:

```powershell
docker compose -f infrastructure/compose.public.yml up -d --build
```

Open http://localhost:3002. This is a **read-only synthetic snapshot**, including
bundled source PDFs, not your private database. All mutation methods are rejected,
even with operator/integration credentials. Restarting preserves the same dataset.
The original writable operator dashboard remains on http://localhost:3000.

The initial commit is local. GitHub rejected the stored credential; the owner
authorized continuing locally and deferring publication until access is restored.

## Local setup with Docker

Requires Docker Desktop with its engine running, Python 3.12+ for the optional
credential-generation helper, and Git. Run from this repository root:

```powershell
python scripts/setup_local.py
docker compose up -d --build
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.seed
docker compose exec backend python -m app.smoke
```

The setup helper generates random passwords into ignored `.env`; it will never
overwrite an existing file or print secrets. Alternatively copy `.env.example`
to `.env`, replace all `CHANGE_ME` values, and use the same database password in
`POSTGRES_PASSWORD` and `DATABASE_URL` (URL-encode special characters).

Open http://localhost:8000/docs and sign in with the operator credentials in your
local `.env`. `GET /health` is public; operator routes, including API docs and
original files, require HTTP Basic. Compose publishes only localhost ports.
Health readiness becomes successful after migrations have run.

Start the dashboard after migration:

```powershell
docker compose --profile dashboard up -d --build frontend
```

Open http://localhost:3000 and sign in with the same local operator credentials.
The dashboard keeps credentials in tab memory and clears them on reload/sign-out.
Use synthetic fixtures for mock extraction. It works with n8n stopped.
For fast frontend development, run `npm.cmd ci` and `npm.cmd run dev` in `frontend/`.
See [frontend setup and browser tests](frontend/README.md).

Optional automation: [n8n setup, credentials and smoke test](n8n/README.md).
Neither the integration key nor the workflow can approve or post invoices.

PostgreSQL uses a named volume and port **5433** on the host; the backend connects
to `postgres:5432` within Compose. Private files use a separate named volume.
`docker compose down` stops the stack and retains both volumes.

Use the API docs to upload `fixtures/invoices/clean-001.pdf`. A repeated upload
returns `200` and the existing ID; a first upload returns `201`. Repeating the
seed command likewise returns the existing invoice. `--all` ingests every fixture,
but **does not automatically process** them. Use the authenticated
`POST /api/v1/invoices/{id}/process` endpoint to extract and validate an invoice.
`python -m app.smoke` demonstrates blocked duplicate approval/posting and rejection,
clean posting, a wrong total corrected from 2500.00 to 2300.00, current-revision
approval, idempotent posting, audit diffs and CSV. It requires mock mode and writes
synthetic internal ledger records only. Repeating it returns the same ledger IDs.

## Host development on Windows

Run PostgreSQL through Compose, then run the API and tests with the local Python
environment. These commands work without activating PowerShell scripts:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
python scripts/setup_local.py
docker compose up -d --wait postgres
.\.venv\Scripts\python.exe scripts/dev.py migrate
.\.venv\Scripts\python.exe scripts/dev.py seed
.\.venv\Scripts\python.exe scripts/dev.py serve
```

Skip the setup helper if `.env` already exists. `scripts/dev.py` loads the root
`.env` without printing its values, translates Compose's `postgres` hostname to
`localhost:5433`, and puts private host files under ignored `storage/uploads`.
Explicit process environment values take precedence. It does not start Docker.
Use either the host API or the container API for a given demo. Their upload
directories differ; switching modes with an existing database requires copying
the private files to the corresponding storage location.

## Tests and checks

```powershell
# Non-database tests; PostgreSQL tests are explicitly skipped without TEST_DATABASE_URL.
.\.venv\Scripts\python.exe scripts/dev.py test

# All tests, using isolated temporary PostgreSQL schemas.
.\.venv\Scripts\python.exe scripts/dev.py test --postgres

.\.venv\Scripts\python.exe -m ruff check backend scripts
.\.venv\Scripts\python.exe -m ruff format --check backend scripts
```

For a container-only test run:

```powershell
docker compose exec backend python -c "import os,pytest; os.environ['TEST_DATABASE_URL']=os.environ['DATABASE_URL']; raise SystemExit(pytest.main(['-q']))"
```

On systems with GNU Make, `make up`, `make migrate`, `make seed`, `make test`,
`make demo`, and `make down` wrap the corresponding Docker commands. `make demo`
demonstrates ingestion, validation, review, posting, audit and export through the API.

Tests cover format/signature rejection, genuine images, malformed files, size
limits including chunked uploads, authentication, CORS, path traversal, migration
round trips and ORM alignment, full upload/read/download/audit flow, concurrent
identical uploads, repeatable vendor seeding, rollback/file cleanup, audit
immutability, and database ledger uniqueness. Day 2 also covers rule boundaries,
invalid AI output, the real Gemini SDK wire format with a fake HTTP transport,
bounded retries, extraction failures, idempotent processing, concurrent requests,
expired processing attempts, and protection against stale workers.
Day 3 tests cover fresh posting checks, approval blockers, revision/payload matching,
simultaneous posts/edits/approvals, ledger rollback and uniqueness, terminal states,
immutable reviews/ledger rows, snapshot-based CSV, quoting and formula protection.
Integration tests require a database
role that can create and drop schemas. They do not clear existing application tables.

`backend/requirements.txt` pins all resolved Python dependencies; `requirements.in`
records direct dependency ranges. Regenerate deterministic PDFs and answer keys
with `python scripts/generate_fixtures.py` (standard library only).

## Current API

| Route | Function |
| --- | --- |
| `GET /health` | Database/migration readiness |
| `POST /api/v1/invoices/upload` | Validate and ingest multipart `file` |
| `POST /api/v1/integrations/n8n/invoices` | Separate integration key, durable idempotency key, upload and processing |
| `POST /api/v1/invoices/{id}/process` | Extract, validate, and persist results; `?retry=true` retries failures |
| `GET /api/v1/invoices` | Filter by status/current issue, filename/vendor/invoice-number search, page and limit |
| `GET /api/v1/invoices/{id}` | Metadata, current payload and validations |
| `GET /api/v1/invoices/{id}/file` | Authenticated original attachment |
| `GET /api/v1/invoices/{id}/audit` | Append-only event history |
| `PATCH /api/v1/invoices/{id}` | Audited field corrections with expected revision |
| `POST /api/v1/invoices/{id}/revalidate` | Fresh checks for the expected revision |
| `POST /api/v1/invoices/{id}/review` | Approve/reject the expected revision; rejects require notes |
| `POST /api/v1/invoices/{id}/post` | Fresh validation and atomic, idempotent ledger posting |
| `GET /api/v1/vendors` | Supplier registry |
| `POST /api/v1/vendors` | Register supplier/policy with an audit event |
| `GET /api/v1/ledger` | Posted ledger rows with page/limit |
| `GET /api/v1/ledger/export.csv` | Download posted records with CSV formula protection |
| `GET /api/v1/stats` | State counts and separate totals per currency |

Errors use `{ "error": { "code": "...", "message": "..." } }`. Processing returns
HTTP 200 with the persisted invoice state and attempt/error code, including an
`EXTRACTION_FAILED` result. Invalid state/retry actions return HTTP 409.
Invoice detail includes current/extracted data, rules with expected/observed values,
processing/review history and linked ledger ID. Unprocessed invoices still have null
payloads. Current validation results belong to one batch; prior batches remain in
the database and their run IDs are recorded in audits.

## Corrections, review and posting

All actions require the authenticated local operator. Read the current revision
from invoice detail and send it as `expected_revision`. The server assigns reviewer
identity from authentication; caller-supplied identities and override flags are rejected.

Example bodies for a newly processed wrong-total invoice:

```json
{"expected_revision":1,"changes":{"total":"2300.00"},"notes":"Subtotal plus tax checked"}
```

Send this to `PATCH /api/v1/invoices/{id}`. Only extraction fields are editable;
nested objects/line-item arrays are replaced as complete field values. A real edit
increments the revision, preserves original extraction, records before/after diffs,
sets `review_required`, clears current validation, and enters `NEEDS_REVIEW`.
An identical-value correction records a no-change audit without incrementing revision.

Then submit to `/revalidate`, `/review`, and `/post`, respectively:

```json
{"expected_revision":2}
```

```json
{"expected_revision":2,"decision":"APPROVE","notes":"Corrected total verified"}
```

```json
{"expected_revision":2}
```

Corrections must be explicitly revalidated before approval/posting. Approval runs
fresh checks and binds the current revision and canonical payload SHA-256. It cannot
waive arithmetic, vendor, duplicate or other blockers. Corrected/flagged invoices
stay `NEEDS_REVIEW` after passing revalidation until that payload is approved.
Another real edit invalidates the previous approval by creating a new revision.

Reject with `decision: "REJECT"` and non-empty notes. A ready invoice first enters
review and is then rejected in the same audited transaction. Rejection is terminal.
Repeated identical reviews return the same decision; recorded review notes cannot
be silently changed. Stale revisions and terminal edits return HTTP 409.

Posting locks the invoice and normalized business identity, checks supplier policy
under a shared row lock, and re-runs all blocking rules inside the transaction.
Ledger insert, `POSTED` transition and audit events commit atomically. A blocker
returns 409 and persists fresh failed checks and the review state. A missing current
approval also returns 409. Database uniqueness independently protects invoice ID and
supplier/invoice number; conflicts roll back partial writes and return to review.
Retried posting returns the same ledger ID. Clean, never-flagged invoices may be
posted explicitly without a separate review decision. Automatic posting is not
implemented; keep `AUTO_POST_CLEAN=false`.

Register an approved unknown supplier with `POST /api/v1/vendors` (all synthetic):

```json
{"display_name":"Unregistered Supplier 1","expected_currency":"USD","baseline_amount_limit":"5000.00","is_approved":true}
```

Supplier names use the same exact normalization as invoice validation. Amount
thresholds require a currency; JPY thresholds must be whole yen. Registration is
audited and does not waive invoice rules. Revalidate and approve the held invoice.

Ledger rows retain the posted payload/revision snapshot, so subsequent registry
display-name changes do not alter exports. The CSV includes only posted entries,
quotes embedded commas/quotes/newlines, uses UTF-8 with BOM, and prefixes potentially
active formula cells with an apostrophe (including leading whitespace/control and
Unicode variants). Filename dates and timestamps use UTC. Export is generated in
memory for this small demo; it is not a large-ledger streaming implementation.
Statistics keep totals separated by currency and are dashboard summaries, not a
cross-currency financial aggregate.

## Extraction and retry behavior

Mock mode requires no external credentials. The adapter resolves the **actual file
SHA-256**, not its uploaded filename. Unknown files fail explicitly with
`MOCK_FIXTURE_NOT_FOUND`; the failure fixture produces `MOCK_EXTRACTION_FAILED`.
No guessed extraction is returned for an unknown document.

The processing endpoint runs synchronously. The `EXTRACTING` state and attempt are
committed before model I/O, so another request can observe processing in progress.
Concurrent requests for the same invoice return the running attempt instead of
launching another extraction. Completed extraction results are idempotent and never
overwritten by another process call. Terminal invoices reject re-extraction.

Failed extraction requires an explicit `?retry=true` request. If a worker or server
dies while extracting, wait two minutes from the attempt start and retry explicitly.
The old attempt is marked failed with `PROCESSING_INTERRUPTED`. A late old worker
cannot overwrite a newer attempt. There is no automatic retry worker in this milestone.

For optional live Gemini extraction, set these in ignored `.env`, choosing a model
supported by your account, then recreate the backend:

```dotenv
AI_MODE=gemini
GEMINI_API_KEY=YOUR_LOCAL_KEY
GEMINI_MODEL=YOUR_SUPPORTED_MODEL
GEMINI_TIMEOUT_SECONDS=10
GEMINI_MAX_ATTEMPTS=3
```

```powershell
docker compose up -d --force-recreate backend
```

The official `google-genai` SDK sends inline document bytes and a fixed structured
schema; the response is validated locally again. Money must be decimal strings,
not JSON floats. The adapter uses at most three attempts and a configured HTTP
timeout per attempt (1–15 seconds), with bounded jittered delays for transient
transport/429/5xx failures. SDK-internal retries are disabled. Allow a longer client
timeout (for example, 60 seconds) for live requests; there is no latency guarantee.
Provider exception text and raw responses are not logged or stored in attempt errors.
Missing key/model configuration becomes `GEMINI_NOT_CONFIGURED`, with no API call.

## Validation policy

Rules run in fixed order, use Decimal arithmetic, and record passed and failed checks.
They cover required fields, ISO/calendar dates and date order, quantity/price and
subtotal/total/tax arithmetic, supported currency/precision, negative values and
ledger range, approved supplier, normalized supplier/invoice duplicate identity,
supplier currency and amount threshold, and uncertainty/missing source evidence.
Missing arithmetic inputs require review; an absent tax rate is never inferred.
The simple explicit-rate calculation assumes the full subtotal is taxable.

Supported currencies are USD, EUR, GBP (two decimal places) and JPY (zero decimal
places). Three-decimal currencies are blocked because the current ledger is
`numeric(18,2)`. `MONEY_TOLERANCE` applies only to USD (0–0.01); EUR/GBP use one cent
and JPY uses exact integer comparisons after rounding. Unit prices and quantities
may contain up to six decimal places. Thresholds are never compared across currencies.

Normalization uses Unicode NFKC, case folding, and collapsed whitespace; punctuation
is preserved. There is no fuzzy supplier approval. Business duplicates are detected
against other active invoices and ledger identities, independent of total. Exact
file repeats still return the original invoice at ingestion. Rejected/failed invoice
peers are excluded from active duplicate checks. Validation is a snapshot; posting
rechecks blockers inside its transaction. An exception sets the sticky
`review_required` flag. Reject an active duplicate before trying to post its original;
if the original was flagged in the meantime, it also requires current review.

Evidence is a short source snippet, not proof of source truth or calibrated AI
confidence. Multi-rate tax, shipping/discount allocation, credit notes, and OCR
training remain outside the MVP. Reviewers are accountable for manual corrections
that disagree with the document; approval records a human decision, not authenticity.

## Limits

Synthetic demonstration only. No cloud/public deployment has been performed.
The public-mode configuration is read-only. Private operators use Argon2id-backed
login with HttpOnly JWT cookies, PostgreSQL sessions, refresh rotation and CSRF
protection. Integration intake instead requires `X-Integration-Key` and
`Idempotency-Key`; those keys do not grant operator access.
Windows filesystem permissions
inherit from the local account; POSIX modes also restrict files in Linux containers.
Normal DB failures clean up new files; crash recovery for orphaned files is pending.
Database triggers protect audit, review, and ledger rows against ordinary UPDATE/
DELETE, not an administrator changing the schema. No malware scanning, payments,
or ERP integration is provided. The operator dashboard is writable only after
authentication. Publish only the separate public-mode configuration; the writable
local stack is not public production authentication.

See [architecture](docs/architecture.md) for decisions and
[Day 1 progress](docs/day-1-progress.md), [Day 2 progress](docs/day-2-progress.md),
and [Day 3 progress](docs/day-3-progress.md), [Day 4 progress](docs/day-4-progress.md)
and [Day 5 progress](docs/day-5-progress.md)
for actually executed checks.

## Layout

- `backend/`: API, business rules, database migrations, and tests.
- `frontend/`: dashboard.
- `n8n/`: automation workflows.
- `infrastructure/`: deployment configuration.
- `docs/`: supplied requirements and project documentation.

The supplied requirements are preserved in `docs/PROJECT_SPEC.md` and
`docs/CODEX_START_HERE.md` for subsequent implementation.

## Configuration

`.env.example` contains placeholders only. Use the setup helper or copy it to `.env`
and replace all `CHANGE_ME` values. Never commit real secrets
or client documents.
