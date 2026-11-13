# Invoice Exception Desk dashboard

Next.js App Router, TypeScript, Tailwind CSS. Uses the authenticated FastAPI API;
all business rules and ledger writes stay in the backend. No frontend API keys.

## Run locally

Start/migrate/seed the backend as described in the root README. Node 22+ required.

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

Open http://localhost:3000, then enter `DEMO_BASIC_USER` and
`DEMO_BASIC_PASSWORD` from the root ignored `.env`. Credentials remain in React
memory; reload/sign out clears the session. Every tab signs in independently.
Both localhost:3000 and 127.0.0.1:3000 are allowed local origins. Other frontend
origins require an explicit `CORS_ORIGINS` entry in the root `.env`; Compose passes
that setting to the backend. Recreate the backend after changing it.

For Docker, from the repository root:

```powershell
docker compose --profile dashboard up -d --build frontend
```

This builds the static export and serves it through nginx on localhost:3000.
The profile is optional so backend-only commands remain lightweight.

`NEXT_PUBLIC_API_BASE_URL` defaults to `http://localhost:8000`. It is a **build-time
public URL**, never a place for credentials. Set it in the shell for host builds
or root `.env` for Compose, then rebuild. It must point to an API address reachable
by the browser, not Docker's `backend` hostname. A public host will require HTTPS
and the Day 5 read-only access policy before publishing.

## Screens and interaction

- `/`: state counts, current duplicate failures, per-currency ledger totals, recent activity.
- `/invoices/`: paginated search, status/issue filtering, direct upload and processing.
- `/exceptions/`: needs-review queue with issue filtering.
- `/invoices/detail/?id=UUID`: protected source preview/download, original extraction,
  editable fields/lines/evidence, validation expected/observed, corrections, revalidation,
  revision-bound approval/rejection, explicit posting, and audit history.
- `/ledger/`: posted snapshots and sanitized CSV export.
- `/vendors/`: supplier policy list and audited registration.

The query-string detail route is intentional: arbitrary runtime UUID paths cannot
be generated ahead of time for the required static export. Links always include
the invoice ID. Refreshing requires signing in again, then opens the requested detail.

Money remains decimal strings, including form edits; the UI does not calculate or
round financial values. Action eligibility is a usability hint; FastAPI rechecks
revision, blockers and policy. A 409 reloads the latest server state and explains
the conflict. There is no automatic polling or posting. Use Refresh to observe a
running extraction; an interrupted attempt requires the backend's explicit retry lease.
Only supplied fixture bytes are recognized in mock mode.

## Checks

```powershell
npm.cmd run typecheck
npm.cmd run build
npx.cmd playwright install chromium
npm.cmd run test:e2e
```

After starting the Docker dashboard and seeding at least one fixture, a read-only
check against the actual built local stack is also available from the root:
`node scripts/check_dashboard.mjs`. It reads the local operator credentials
privately, checks login/data/detail navigation/mobile containment, and saves
synthetic screenshots under ignored `storage/previews/`.

Build output is `out/`. Serve it as static files or use the Docker profile;
`next start` does not serve a static export.

Browser tests need the root Python `.venv` dependencies and running PostgreSQL.
They start a temporary API on port 8001, frontend on 3001, and a random database
schema with test-only credentials. They use synthetic fixtures and never reset the
demo schema. Teardown removes the tracked test schema even when Windows terminates
the server process. If a test runner itself is forcibly killed, run
`../.venv/Scripts/python.exe ../scripts/browser_api.py --cleanup` from this directory.
Set `TEST_DATABASE_URL` to override the database connection. Only the loopback
Compose hostname is translated for host access.

Tests exercise real API upload/process, clean posting, correction/revalidation/
approval/posting, duplicate blocking/rejection, immutable fields, audit, CSV download,
supplier registration, invalid login, mobile overflow, filters and sign-out. Traces
and screenshots stay under ignored `test-results/` and `storage/previews/`.

References: [Next.js styling](https://nextjs.org/docs/app/getting-started/css),
[static exports](https://nextjs.org/docs/app/guides/static-exports).
