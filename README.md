# Invoice Exception Desk

Catch invoice mistakes before they reach your ledger.

An invoice exception-management demonstration using synthetic invoices.
Day 1 implements secure ingestion and the database foundation.

## Stack

- Backend: FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, PostgreSQL 16.
- Frontend: Next.js, TypeScript, Tailwind CSS.
- Extraction: deterministic mock adapter, optional Gemini adapter.
- Automation: optional n8n Gmail ingestion and notifications.

## Current status

Implemented: FastAPI, PostgreSQL models and Alembic migration, private PDF/JPG/PNG
upload (8 MiB), SHA-256 deduplication, authenticated invoice list/detail/download,
audit history, supplier list, an idempotent seed CLI, and 16 synthetic PDFs with
deterministic answer keys. All uploaded invoices remain `RECEIVED` in Day 1.

Pending: extraction adapters and rules (Day 2), corrections/reviews/posting/CSV
(Day 3), Next.js dashboard and n8n workflows (Day 4), portfolio deployment and QA
(Day 5). No Gemini, Gmail, Telegram, or n8n integration is connected.

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
but **does not extract, validate, approve, or post** any of them yet.

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
currently demonstrates ingestion only; the complete business flow is a later milestone.

Tests cover format/signature rejection, genuine images, malformed files, size
limits including chunked uploads, authentication, CORS, path traversal, migration
round trips and ORM alignment, full upload/read/download/audit flow, concurrent
identical uploads, repeatable vendor seeding, rollback/file cleanup, audit
immutability, and database ledger uniqueness. Integration tests require a database
role that can create and drop schemas. They do not clear existing application tables.

`backend/requirements.txt` pins all resolved Python dependencies; `requirements.in`
records direct dependency ranges. Regenerate deterministic PDFs and answer keys
with `python scripts/generate_fixtures.py` (standard library only).

## Current API

| Route | Function |
| --- | --- |
| `GET /health` | Database/migration readiness |
| `POST /api/v1/invoices/upload` | Validate and ingest multipart `file` |
| `GET /api/v1/invoices` | Filter by status, filename search, page and limit |
| `GET /api/v1/invoices/{id}` | Metadata, current payload and validations |
| `GET /api/v1/invoices/{id}/file` | Authenticated original attachment |
| `GET /api/v1/invoices/{id}/audit` | Append-only event history |
| `GET /api/v1/vendors` | Seeded suppliers |

Errors use `{ "error": { "code": "...", "message": "..." } }`. Invoice detail
returns null extraction/current payloads and no validation results until Day 2.
Filename search will expand to extracted supplier/invoice fields in a later milestone.

## Limits

Synthetic local demonstration only. No public dashboard or public write endpoints
are deployed. Basic auth is for the local operator. Windows filesystem permissions
inherit from the local account; POSIX modes also restrict files in Linux containers.
Normal DB failures clean up new files; crash recovery for orphaned files is pending.
The database audit trigger prevents ordinary UPDATE/DELETE, not an administrator
changing the schema. No malware scanning, payments, or ERP integration is provided.

See [architecture](docs/architecture.md) for decisions and
[Day 1 progress](docs/day-1-progress.md) for actually executed checks.

## Layout

- `backend/`: API, business rules, database migrations, and tests.
- `frontend/`: dashboard.
- `n8n/`: automation workflows.
- `infrastructure/`: deployment configuration.
- `docs/`: supplied requirements and project documentation.

The supplied requirements are preserved in `docs/PROJECT_SPEC.md` and
`docs/CODEX_START_HERE.md` for subsequent implementation.

## Configuration

`.env.example` contains placeholders only. Copy it to `.env` when local setup
is implemented, and replace all `CHANGE_ME` values. Never commit real secrets
or client documents.
