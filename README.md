# Invoice Exception Desk

Catch invoice mistakes before they reach your ledger.

Repository setup for an invoice ingestion, extraction, validation, human review,
and audit demonstration using synthetic invoices.

## Planned stack

- Backend: FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, PostgreSQL 16.
- Frontend: Next.js, TypeScript, Tailwind CSS.
- Extraction: deterministic mock adapter, optional Gemini adapter.
- Automation: optional n8n Gmail ingestion and notifications.

## Current status

Repository initialization only. Application implementation has not started.
No services, integrations, migrations, or application tests are available yet.
The initial repository must be pushed before application development begins.

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
