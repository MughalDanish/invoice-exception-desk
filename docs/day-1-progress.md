# Day 1: foundation

Scope: the supplied implementation brief requests Day 1 only, with an actual
results report before Day 2. All work is isolated in this independent repository
on `feature/invoice-exception-desk`. Existing sibling applications are unchanged.

## Files and implemented behavior

- `backend/app/core/`: environment configuration, operator authentication,
  structured errors, and bounded HTTP request bodies.
- `backend/app/db/`: SQLAlchemy 2 models and session lifecycle.
- `backend/alembic/`: explicit reversible initial PostgreSQL migration, including
  partial delivery uniqueness, file hash uniqueness, ledger uniqueness, and
  append-only audit trigger.
- `backend/app/modules/invoices/`: file format validation, private UUID storage,
  transactional ingestion/deduplication, list/detail/download endpoints.
- `backend/app/modules/audit/`: transactional audit events.
- `backend/app/seed.py`: repeatable three-vendor seed and fixture ingestion.
- `fixtures/`: 16 synthetic PDFs and hash-indexed extraction answer keys. There
  are 15 distinct byte hashes because one fixture deliberately copies another.
- `backend/tests/`: safety/auth/API and PostgreSQL migration/concurrency tests.
- `docker-compose.yml`, `backend/Dockerfile`, `.dockerignore`, `Makefile`:
  local PostgreSQL and non-root backend containers, volumes, and commands.
- `scripts/`: safe local credential generation, reproducible fixtures, and
  Windows-friendly host commands.
- `README.md`, `docs/architecture.md`, and milestone notes for frontend, n8n,
  and infrastructure: exact commands, design decisions, and remaining work.
- `backend/requirements.txt`: pinned dependencies; `.env.example`: placeholders.

## Checks

Initial executed checks:

| Command | Actual result |
| --- | --- |
| `python scripts/generate_fixtures.py` | Generated 16 synthetic PDFs and answer keys |
| `.venv/Scripts/python.exe -m pip check` | No broken requirements |
| `.venv/Scripts/python.exe -m ruff check backend scripts` | Passed |
| `.venv/Scripts/python.exe -m ruff format --check backend scripts` | Passed |
| `.venv/Scripts/python.exe scripts/dev.py test` | 26 passed, 11 PostgreSQL tests skipped before the additional ledger test was added |
| `.venv/Scripts/python.exe -m alembic -c backend/alembic.ini upgrade head --sql` | Generated PostgreSQL migration SQL; this alone is not a DB execution |

The initial chunked-upload test exposed an incorrect 400 response for oversized
bodies. Error propagation was fixed and the test now verifies HTTP 413.

The installed Starlette version emits a deprecation warning for its HTTPX
TestClient compatibility path; this does not fail the checks.

Final container verification:

| Command | Actual result |
| --- | --- |
| `docker compose config --quiet` | Compose configuration valid |
| `docker compose up -d --wait postgres` | PostgreSQL healthy after initial image download |
| `docker compose build backend` | Linux image built successfully with pinned dependencies |
| `docker compose up -d backend` | Backend started as non-root user |
| `docker compose exec -T backend alembic upgrade head` | Applied `0001_foundation` on PostgreSQL |
| `docker compose exec -T backend python -m app.seed` (twice) | First created invoice; second returned the same ID with `duplicate: true` |
| `docker compose exec -T backend python -c "import os,pytest; os.environ['TEST_DATABASE_URL']=os.environ['DATABASE_URL']; raise SystemExit(pytest.main(['-q','-x','--tb=short']))"` | **38 passed**, 2 non-failing warnings |
| `docker compose exec -T backend python -m app.smoke` | Live health, authentication, repeated upload, exact original download, and audit history passed |
| `docker compose ps` | Backend and PostgreSQL both healthy on localhost |
| Final Ruff lint / format / pip checks | Passed; 30 Python files formatted, no broken requirements |
| Staged PDF hashes / local-credential scan / Git whitespace check | Passed; fixture bytes preserved, generated credentials excluded |

The second Linux warning is an unwritable optional pytest cache directory in the
non-root container; the complete test suite passes. It does not affect API or
database behavior.

The first elevated Windows DB run hit pytest shared temporary-directory ACLs
(10 passed, 28 setup errors). The host runner now creates a fresh temporary
directory per invocation and disables shared pytest caching. No application
test assertion failed in that run; successful DB checks included migration/ORM
alignment, migration round trip, and audit immutability. The verification rerun
with `.venv/Scripts/python.exe scripts/dev.py test --postgres` passed:
**38 passed, 1 deprecation warning**. No tests were skipped in either final
PostgreSQL run (Windows host and Linux container).

The running Day 1 demo is available at `http://localhost:8000/docs` with the
locally generated operator credentials in ignored `.env`. The database has
three approved synthetic suppliers and one `RECEIVED` invoice. No ledger rows
were posted by the demo.

## Remaining milestones

- Day 2: extraction protocol, deterministic mock adapter, Gemini adapter,
  Pydantic extraction schemas, deterministic rules, processing/retry state changes.
- Day 3: corrections, revision checks, approvals/rejections, atomic validated
  posting, CSV export, and posting race tests.
- Day 4: working Next.js dashboard, n8n workflow exports, and mock end-to-end demo.
- Day 5: full fixture benchmark, deployment configurations and read-only demo mode,
  portfolio materials, final QA and demo script.

No live AI or messaging credentials are needed for Day 1. Gemini, Gmail,
Telegram, and n8n are not connected. `AI_MODE=mock` is configuration only at this
milestone; extraction is not implemented yet. No payments, public deployment,
or financial posting was performed.

GitHub publication remains blocked by the previously rejected saved login. The
owner explicitly authorized local work and publication when GitHub is connected.
