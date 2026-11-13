# Invoice Exception Desk

Catch invoice mistakes before they reach your ledger.

An invoice exception-management demonstration using synthetic invoices.
Days 1–2 implement secure ingestion, extraction, validation, and processing recovery.

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

Pending: corrections/reviews/posting/CSV (Day 3), Next.js dashboard and n8n workflows
(Day 4), portfolio deployment and QA (Day 5). Gemini's request construction and
failure handling are tested offline with the real SDK and a fake HTTP transport;
live extraction has not been verified. Gmail, Telegram, and n8n are not connected.

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
local `.env`. `GET /health` is public; all other routes, including API docs and
original files, require HTTP Basic. Compose publishes only localhost ports.
Health readiness becomes successful after migrations have run.

PostgreSQL uses a named volume and port **5433** on the host; the backend connects
to `postgres:5432` within Compose. Private files use a separate named volume.
`docker compose down` stops the stack and retains both volumes.

Use the API docs to upload `fixtures/invoices/clean-001.pdf`. A repeated upload
returns `200` and the existing ID; a first upload returns `201`. Repeating the
seed command likewise returns the existing invoice. `--all` ingests every fixture,
but **does not automatically process** them. Use the authenticated
`POST /api/v1/invoices/{id}/process` endpoint to extract and validate an invoice.
`python -m app.smoke` demonstrates a clean invoice becoming ready, an incorrect
total requiring review, and an altered business duplicate requiring review.
It requires mock mode and never posts ledger entries.

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
currently demonstrates ingestion and validation; review and posting are a later milestone.

Tests cover format/signature rejection, genuine images, malformed files, size
limits including chunked uploads, authentication, CORS, path traversal, migration
round trips and ORM alignment, full upload/read/download/audit flow, concurrent
identical uploads, repeatable vendor seeding, rollback/file cleanup, audit
immutability, and database ledger uniqueness. Day 2 also covers rule boundaries,
invalid AI output, the real Gemini SDK wire format with a fake HTTP transport,
bounded retries, extraction failures, idempotent processing, concurrent requests,
expired processing attempts, and protection against stale workers.
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
| `POST /api/v1/invoices/{id}/process` | Extract, validate, and persist results; `?retry=true` retries failures |
| `GET /api/v1/invoices` | Filter by status, filename/vendor/invoice-number search, page and limit |
| `GET /api/v1/invoices/{id}` | Metadata, current payload and validations |
| `GET /api/v1/invoices/{id}/file` | Authenticated original attachment |
| `GET /api/v1/invoices/{id}/audit` | Append-only event history |
| `GET /api/v1/vendors` | Seeded suppliers |

Errors use `{ "error": { "code": "...", "message": "..." } }`. Processing returns
HTTP 200 with the persisted invoice state and attempt/error code, including an
`EXTRACTION_FAILED` result. Invalid state/retry actions return HTTP 409.
Invoice detail includes current/extracted data, rules with expected/observed values,
and processing-attempt history. Unprocessed invoices still have null payloads.

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
peers are excluded from active duplicate checks. Validation is a snapshot; Day 3
posting must recheck blockers inside its transaction. An exception sets the sticky
`review_required` flag for the later correction/approval flow.

Evidence is a short source snippet, not proof of source truth or calibrated AI
confidence. Multi-rate tax, shipping/discount allocation, credit notes, and OCR
training remain outside the MVP. No approval or posting API exists in Day 2.

## Limits

Synthetic local demonstration only. No public dashboard or public write endpoints
are deployed. Basic auth is for the local operator. Windows filesystem permissions
inherit from the local account; POSIX modes also restrict files in Linux containers.
Normal DB failures clean up new files; crash recovery for orphaned files is pending.
The database audit trigger prevents ordinary UPDATE/DELETE, not an administrator
changing the schema. No malware scanning, payments, or ERP integration is provided.

See [architecture](docs/architecture.md) for decisions and
[Day 1 progress](docs/day-1-progress.md) and [Day 2 progress](docs/day-2-progress.md)
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
