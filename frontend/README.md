# Frontend maintenance

The UI keeps the Theme B palette and uses self-hosted Inter, Tailwind, shadcn/Radix, Lucide, TanStack Query/Table, React Hook Form, Zod, Recharts and Sonner. All changes are frontend presentation or orchestration; financial rules remain on the backend.

## Follow a request through the application

`app/layout.tsx` → `providers/app-providers.tsx` → `components/desk.tsx` → screen → feature query hook → `lib/api.ts` → backend.

- `components/desk.tsx`: authentication boundary, shadcn sidebar/mobile Sheet, breadcrumbs and technical drawer. Each session gets a fresh in-memory QueryClient; sign-out cancels requests and clears protected caches.
- `lib/query/client.ts`: read retries, request lifetimes, configurable cache defaults and unauthorized handling. Cache settings use build-time `NEXT_PUBLIC_QUERY_STALE_TIME_MS` and `NEXT_PUBLIC_QUERY_GC_TIME_MS` (15 seconds and 5 minutes by default).
- `lib/query/keys.ts`: resource key factories. Include pagination and filters in keys so independent worklists cannot overwrite each other.
- `features/*/queries.ts`: feature reads and mutations. Queries pass cancellation signals. Mutations never retry, queue or optimistically approve/post. Success follows a backend response; targeted invalidation refreshes affected resources.
- `features/invoices/invalidation.ts`: saving refreshes detail, audit, invoice lists and overview; posting also refreshes the ledger. Original document and unrelated supplier/detail caches stay intact.
- `features/invoices/polling.ts`: poll only recent active extraction, with a four-minute bound; terminal invoices do not poll.

## Change one area independently

- Navigation: edit the navigation configuration in `components/desk.tsx`.
- Theme and density: semantic tokens and layouts in `app/globals.css`; Inter and its license are in `public/fonts`.
- Operational tables: `components/shared/data-table.tsx` renders shadcn Table using TanStack Table. `features/invoices/invoice-table.tsx` owns invoice columns and independent action menus. Invoice/ledger pagination is server-controlled; supplier search/sort covers the complete returned registry.
- Review: `components/invoice-detail.tsx` composes source preview, resizable panels and tabs. `features/invoices/components/invoice-editor.tsx` owns the React Hook Form draft, draft revision baseline and confirmations. An external revision change preserves edits and requires an explicit reload. Unsaved edits cannot be approved or posted.
- Source preview: `features/invoices/components/document-preview.tsx` consumes the document query and owns only its temporary browser object URL. PDF rendering uses the browser's native viewer; open/download actions provide access to the original file.
- Financial evidence: pure adapters in `lib/presentation.ts` group decimal strings without numeric conversion or rounding. `components/evidence` presents original extraction, failed-first validation and compact audit history. Full payloads remain in the technical Sheet with copy/manual-selection actions.
- Loading: `components/shared/loading.tsx` supplies screen skeletons, background indicators, paused/offline states and indeterminate processing. `components/ui/button.tsx` adds pending states to the standard shadcn Button. Route progress is completed from router state and bounded on failure/cancellation.

## Verify changes (from this directory)

```powershell
npm.cmd run typecheck
npm.cmd run lint
npm.cmd run test:unit
npm.cmd run test:e2e
$env:PUBLIC_PREVIEW='true'; npm.cmd run test:e2e -- --config playwright.public.config.ts
npm.cmd run build
```

The operator suite creates and removes its own PostgreSQL schema and temporary files. It never resets demo records. The public suite uses the running read-only preview on port 3002. On Windows, allow normal subprocess permissions so Playwright can terminate its child servers.

Unit tests cover decimal precision, missing/unknown evidence, audit mapping, query deduplication, targeted invalidation, cancellation, session isolation and bounded polling. Browser tests exercise real correction → revalidation → approval → posting, duplicate rejection, CSV export, supplier registration, authentication, mobile navigation, source JSON copying, read-only denial and loading/error recovery.

For local Docker review, run the root dashboard profile on port 3000 or `infrastructure/compose.public.yml` on port 3002. These are local previews; no remote publishing is configured by this redesign.

## Operator authentication

Login and logout use `/api/v1/auth/login` and `/api/v1/auth/logout`; `/auth/me` restores the session after a reload. Access cookies last 24 hours and rotating refresh cookies last 7 days. Both are HttpOnly. PostgreSQL stores Argon2id password hashes and refresh-token hashes; logout and refresh reuse revoke the server session immediately.

`features/auth` owns the user query and login form. `lib/api.ts` includes cookies, obtains an in-memory signed CSRF nonce, deduplicates refresh requests and coordinates tabs with Web Locks. Only explicit pre-handler expired/missing-access responses permit one replay. Business errors and uncertain financial outcomes never trigger automatic mutation retries. Signing out clears the session's protected QueryClient.

Provision the initial local operator after migration from the repository root:

```powershell
docker compose run --rm --no-deps backend python -m alembic upgrade head
docker compose run --rm --no-deps backend python -m app.modules.auth.bootstrap
```

Configure a stable random `AUTH_JWT_SECRET` of at least 32 bytes. `AUTH_BOOTSTRAP_USERNAME` and `AUTH_BOOTSTRAP_PASSWORD` provision a missing account only; rerunning does not reset existing credentials. Use Secure cookies with HTTPS outside localhost. The explicit `AUTH_COOKIE_SECURE=false` setting is for local HTTP development only. No passwords or tokens are persisted in browser storage.
