Read `CODEX_START_HERE.md` and `PROJECT_SPEC.md` completely before implementation, if these files are available. If they are missing, use the complete requirements below as the source of truth. Do not stop merely because those files are unavailable.

# Project: Invoice Exception Desk

Build a fully functional, portfolio-ready **Invoice Exception Desk** application within a strict 3–5-day MVP scope.

The application automates supplier invoice ingestion, AI-powered data extraction, deterministic validation, duplicate detection, human exception review, ledger posting, and audit logging.

The key objective is to demonstrate that the system can **identify incorrect or duplicate invoices and prevent unsafe automatic posting**, rather than merely extracting data from PDFs.

## 1. Repository and Git Setup

Before writing application code:

1. Inspect the current working directory and Git repository.
2. Create a completely separate project folder named `invoice-exception-desk`.
3. Initialize a new, independent Git repository inside that folder. Do not modify the existing project's files or Git history.
4. Create and switch to a development branch named `feature/invoice-exception-desk`.
5. Keep the project isolated from other applications.
6. Organize frontend, backend, automation workflows, infrastructure, and documentation into separate directories.
7. Add a proper `.gitignore`, `.env.example`, and README.
8. Do not commit API keys, secrets, credentials, or generated private data.
9. Do not create or push a remote GitHub repository unless remote access is configured and authorized. If unavailable, prepare the local repository and provide the commands required to publish it.

Use this structure:

```text
invoice-exception-desk/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/
│   │   ├── db/
│   │   └── modules/
│   │       ├── invoices/
│   │       ├── extraction/
│   │       ├── validation/
│   │       ├── approvals/
│   │       ├── ledger/
│   │       └── audit/
│   ├── alembic/
│   ├── tests/
│   └── requirements.txt
├── frontend/
├── n8n/
├── infrastructure/
├── docs/
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

## 2. Architecture

Use a **modular monolith**, not microservices.

- One FastAPI backend owns all business logic.
- PostgreSQL is the authoritative database.
- Next.js provides the dashboard.
- n8n handles Gmail ingestion and optional notifications.
- Gemini extracts structured invoice information.
- FastAPI performs all deterministic validation and controls approval and ledger operations.

Do not introduce Kafka, Kubernetes, Redis, Celery, or unnecessary distributed components.

The application must function independently of n8n. Users should be able to upload invoices directly from the dashboard even when n8n is offline.

## 3. Technology Stack

**Backend**
- Python
- FastAPI
- Pydantic
- SQLAlchemy
- Alembic
- PostgreSQL
- pytest

**Frontend**
- Next.js
- TypeScript
- Tailwind CSS

**Automation**
- n8n Community Edition
- Gmail integration
- Optional Telegram notifications

**AI**
- Gemini API with structured JSON output
- Mock extraction provider when API credentials are unavailable

**Infrastructure**
- Docker Compose for local development
- Render Free Web Service for FastAPI
- Render Static Site for the Next.js static export
- Neon Free PostgreSQL

Keep dependencies minimal and favor established, maintainable libraries.

## 4. Core Application Workflow

Implement this complete sequence:

1. Supplier sends a PDF invoice by Gmail or a user uploads one through the dashboard.
2. The backend stores invoice metadata and securely handles the file.
3. Gemini extracts supplier name, invoice number, dates, currency, line items, subtotal, tax, and total.
4. Pydantic validates the extracted JSON structure.
5. The validation service checks arithmetic, duplicate invoices, supplier status, dates, and required fields.
6. Valid invoices proceed to the internal ledger, subject to configured business rules.
7. Invalid or uncertain invoices enter an exception queue.
8. An authorized user reviews, corrects, approves, or rejects exceptions.
9. Corrected invoices must be revalidated before posting.
10. Every significant action is recorded in an audit log.
11. Approved ledger records can be exported as CSV.

Never allow AI to directly approve payments or bypass validation.

## 5. Invoice Validation Rules

Implement deterministic checks for:

- Subtotal and line-item calculation mismatches.
- Tax and grand-total inconsistencies.
- Duplicate invoices using supplier identity, invoice number, and other relevant fields.
- Unknown or unapproved suppliers.
- Missing required fields.
- Invalid invoice dates.
- Due dates earlier than invoice dates.
- Unexpected currency values.
- Suspiciously high amounts, using configurable rules.
- Invalid or incomplete AI extraction results.

Use decimal arithmetic for financial calculations. Never use floating-point arithmetic for money.

Ensure duplicate prevention is enforced through database constraints and idempotent processing, not merely application-level checks.

## 6. Database and State Management

Create suitable tables for:

- Users
- Suppliers
- Invoices
- Invoice line items
- Validation exceptions
- Approval decisions
- Ledger entries
- Audit logs
- Processing attempts

Use Alembic migrations.

Implement explicit invoice states, such as:

`RECEIVED → EXTRACTING → VALIDATING → POSTED`

For invoices requiring human review:

`VALIDATING → NEEDS_REVIEW → CORRECTED → VALIDATING → POSTED`

Also support rejection and processing failures.

Enforce valid state transitions.

Ledger posting and invoice status updates must be atomic.

Ensure the same invoice cannot generate multiple ledger entries, including under concurrent requests.

## 7. API Requirements

Implement documented endpoints for:

- Uploading invoices.
- Listing invoices with pagination and filtering.
- Retrieving invoice details.
- Viewing extraction results.
- Viewing validation exceptions.
- Correcting invoice fields.
- Approving or rejecting invoices.
- Viewing audit history.
- Listing ledger records.
- Exporting ledger data as CSV.
- Receiving authenticated n8n integration requests.
- Application health checks.

Use FastAPI's OpenAPI documentation.

Apply authentication and authorization to sensitive endpoints.

Use consistent error responses and appropriate HTTP status codes.

## 8. Frontend Requirements

Build a clean, modern finance dashboard with:

**Overview**
- Total invoices.
- Successfully processed invoices.
- Invoices needing review.
- Duplicate invoices.
- Recent activity.

**Invoice List**
- Supplier.
- Invoice number.
- Amount.
- Date.
- Processing status.
- Detected issues.

**Invoice Details**
- Original invoice preview when available.
- Extracted fields.
- Validation results.
- Exception explanations.
- Correction controls.
- Approve/reject actions.

**Exception Queue**
- Filter invoices by issue type.
- Review and correct extracted information.
- Revalidate before posting.

**Ledger**
- Successfully posted invoices.
- CSV export.

**Audit History**
- Processing events.
- Approval decisions.
- Corrections.
- Timestamps and responsible users.

Prioritize usability and clarity. Avoid unnecessary animations or advanced UI features.

## 9. Authentication and Security

Implement two operating modes.

**Local development mode**
- Authenticated dashboard access.
- Full invoice upload, review, approval, and ledger functionality.
- Mock integrations supported.
- Synthetic demo invoices.

**Public portfolio demo mode**
- Read-only access to synthetic invoice data.
- No anonymous upload, approval, deletion, or financial record modification.
- No real client documents.
- No exposed credentials.
- Clearly identify the application as a demonstration.

Additional requirements:
- Protect API secrets using environment variables.
- Validate uploaded files and enforce size limits.
- Avoid relying on user-supplied filenames as storage paths.
- Restrict CORS to configured frontend origins.
- Verify integration credentials.
- Prevent duplicate approvals and stale review actions.
- Maintain immutable audit history for significant operations.
- Do not store confidential invoices on ephemeral hosting.
- Never expose raw Gemini or database credentials to the frontend.

## 10. Mock Mode

The entire core application must work without paid third-party accounts.

Include realistic synthetic invoice fixtures representing:

- Correct invoices.
- Incorrect totals.
- Duplicate invoices.
- Missing invoice numbers.
- Unknown suppliers.
- Invalid dates.
- Extraction failures.

Mock AI extraction must return predictable structured results.

Use the mock mode for automated tests and the public portfolio demonstration.

## 11. n8n Integration

n8n is responsible only for external workflow orchestration.

Implement a workflow that:

1. Monitors a designated Gmail label.
2. Retrieves PDF invoice attachments.
3. Sends them to the authenticated FastAPI ingestion endpoint.
4. Receives processing results.
5. Optionally sends exception notifications through Telegram.
6. Logs integration failures and supports safe retries.

Business rules must remain inside FastAPI, not scattered across n8n nodes.

Provide an importable n8n workflow JSON and clear configuration instructions.

The backend must continue working when n8n is unavailable.

## 12. Free Deployment Strategy

Prepare two deployment configurations.

**Option A — Free portfolio deployment**

- Next.js static export on Render Static Site.
- FastAPI on Render Free Web Service.
- PostgreSQL on Neon Free.
- n8n running locally through Docker.

The public dashboard must function without n8n running.

Account for Render sleeping when idle and its ephemeral filesystem.

Do not depend on persistent local storage for uploaded files. For the public demonstration, use seeded synthetic data and a storage approach that remains available after restarts.

**Option B — Single Linux VM**

Prepare Docker Compose configuration for:

- FastAPI
- Next.js
- n8n
- PostgreSQL, if self-hosted
- Reverse proxy and HTTPS configuration guidance

Do not provision cloud services or incur charges without authorization.

Document the limitations and terms of free hosting, including any restrictions on commercial usage.

## 13. Testing Requirements

Use pytest for backend tests.

Cover:

- Correct invoice calculations.
- Incorrect totals.
- Tax discrepancies.
- Duplicate submissions.
- Concurrent duplicate processing.
- Invalid AI output.
- Unknown suppliers.
- Missing fields.
- Unauthorized approvals.
- Invalid state transitions.
- Approval after corrections.
- Double-posting prevention.
- Database transaction rollback.
- AI API failures.
- n8n integration failures.

Prepare 12–20 synthetic invoices for the MVP.

Build a repeatable demonstration showing three essential scenarios:

1. A correct invoice is automatically recorded.
2. An incorrect invoice is blocked and sent for review.
3. A duplicate invoice is detected and prevented from creating a second ledger record.

Document which tests actually pass and which remain incomplete.

## 14. Five-Day Development Plan

**Day 1 — Foundation**
- Create repository, branch, and folder structure.
- Configure Docker Compose.
- Build FastAPI project.
- Configure PostgreSQL and migrations.
- Create invoice models.
- Implement invoice upload.
- Add synthetic fixtures.

**Day 2 — Extraction and Validation**
- Implement Gemini extraction adapter.
- Implement mock extraction.
- Add Pydantic schemas.
- Build validation rules.
- Implement duplicate detection.
- Write unit tests.

**Day 3 — Review and Ledger**
- Implement invoice state machine.
- Build corrections and approvals.
- Add audit logging.
- Implement idempotent ledger posting.
- Build CSV export.
- Test concurrent operations.

**Day 4 — Dashboard and Automation**
- Build Next.js dashboard.
- Add invoice list and detail views.
- Build exception review interface.
- Implement n8n workflow.
- Configure integrations and mock mode.

**Day 5 — Testing and Deployment**
- Run end-to-end tests.
- Fix critical bugs.
- Prepare deployment configurations.
- Deploy where credentials and access are available.
- Seed demo invoices.
- Capture portfolio screenshots.
- Prepare a two-minute demonstration flow.
- Finalize README and documentation.

Do not expand the MVP beyond these milestones.

## 15. Documentation and Deliverables

The repository must include:

- Working backend.
- Working frontend.
- PostgreSQL migrations.
- Synthetic sample data.
- Mock extraction mode.
- n8n workflow JSON.
- Docker Compose setup.
- Environment variable examples.
- Backend tests.
- API documentation.
- Local setup guide.
- Free deployment guide.
- Architecture diagram.
- Known limitations.
- Upwork portfolio description.
- Two-minute demo script.

## 16. Codex Working Instructions

Follow these rules throughout development:

1. Read the complete specification before implementation.
2. If existing repository files are present, inspect them before making changes.
3. Do not overwrite or modify unrelated projects.
4. Begin with the repository setup and Day 1 milestone.
5. Implement one milestone at a time.
6. Run relevant tests after each milestone.
7. Fix failures before advancing when feasible.
8. Maintain consistent naming and modular separation.
9. Keep the implementation production-minded but MVP-sized.
10. Use mock integrations when external credentials are missing.
11. Do not invent test results or claim deployments succeeded without verification.
12. Do not make unrequested external purchases or provision paid infrastructure.
13. Do not push Git changes without authorization.
14. Create meaningful local commits after completed milestones.
15. If a technical decision is unspecified, choose the simplest secure solution and document the assumption.
16. Do not ask unnecessary questions when a reasonable implementation choice is available.

### Required progress report

After every milestone, report:

- Files created or modified.
- Features implemented.
- Tests executed and their results.
- What is working.
- What remains incomplete.
- Any blockers or credentials required.
- Next milestone.

### Start now

Begin by inspecting the current directory and Git state.

Create the separate `invoice-exception-desk` folder and initialize its independent repository.

Create and switch to `feature/invoice-exception-desk`.

Then implement **Day 1 only**, run tests, and report the actual results before proceeding to Day 2.