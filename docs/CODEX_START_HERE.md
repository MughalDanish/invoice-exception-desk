# Copy this instruction into Codex

Build the **Invoice Exception Desk** described in the attached `PROJECT_SPEC.md`.

You are acting as a senior full-stack engineer. The goal is to produce a **running, tested, portfolio-ready MVP within a strict five-day scope**, not a set of mockup screens or placeholder architecture.

Important constraints:
- Backend: FastAPI + Pydantic v2 + SQLAlchemy 2 + PostgreSQL.
- Frontend: Next.js + TypeScript + Tailwind.
- n8n orchestrates inbound Gmail/webhook integrations; **FastAPI is authoritative for validation, review, ledger state, and audit**.
- Gemini uses an adapter, with `AI_MODE=mock` working without any external credentials.
- Use synthetic invoice fixtures, realistic validation cases, human-reviewed exceptions, idempotent posting, revision checks, and CSV export.
- Authenticated dashboard is the only approval mechanism for MVP. Optional Telegram is for notifications, not approval.
- Prioritize a complete working core. No payments, no ERP writeback, no multi-tenancy, no Redis/Kafka, no invented performance claims.

**Execute, don't only plan**. First inspect repository files, then implement in milestones:
1. Compose environment, backend models, migrations, upload + fixture seed.
2. Extraction adapter, deterministic validation rules, statuses and tests.
3. Correction/review/posting APIs, ledger uniqueness, audit and CSV, tests.
4. Dashboard and n8n workflow JSON, complete end-to-end mock demo.
5. QA, benchmark of test fixtures, docs and demo script.

After each milestone, run real commands/tests and fix failures. If external credentials are absent, keep advancing using mocks and document the exact configuration required for live integrations. Never claim that a simulated feature is live.

At completion, provide a concise checklist of actual working features, exact setup commands, test results, unconnected integrations, and remaining limitations. Read `PROJECT_SPEC.md` for all models, API routes, state transitions, acceptance criteria, UI and packaging details. Resolve minor implementation details yourself without changing the product scope.
