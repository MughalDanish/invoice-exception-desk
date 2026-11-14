# Deployment preparation — no services provisioned

Configuration was prepared and checked locally on 14 November 2026. No Git push,
public hosting, account creation, live model inference or cloud provisioning was performed.

## Two operating modes

The root Compose environment explicitly runs `PUBLIC_DEMO=false`. It keeps the
existing authenticated writable operator API and PostgreSQL ledger. Basic auth is
for local/private demonstration; do not expose that service as a production SaaS.

`PUBLIC_DEMO=true` mounts only the read router over `fixtures/public-demo.json`.
This is a curated read model exported by `app.qa.public_export` from a new isolated
PostgreSQL schema using bundled fixtures and mock extraction. It contains 15 unique
documents from the original 16 submissions (one byte-identical duplicate). It is
not live bookkeeping data. Source previews are hash-verified bundled synthetic
PDFs, never files under `STORAGE_DIR`. No DB engine/model client is constructed.
All HTTP mutations are denied before body parsing, including unknown future routes,
operator credentials and integration keys. CSV export and private API docs are
not exposed. Restarting/redeploying preserves this bundled snapshot and sources.

**Tradeoff:** PostgreSQL remains authoritative for the writable application and
generates the public export. The public serving process deliberately uses the
reviewed, frozen projection rather than live DB rows. This avoids an accidental
private-data publication and any dependence on ephemeral uploads. Changes in a
local ledger do not update the public demo; regenerate/review/redeploy explicitly.

## Option A: Render public portfolio

`render.yaml` prepares a Docker FastAPI service and Next.js static site. Owner
authorization and a connected Git repository are still required before creation.

1. Publish the reviewed repository only when GitHub credentials are available.
2. Review the Render Blueprint in the owner's account. It requests a Free API;
   static hosting uses `frontend/out`. Inspect the dashboard's plan/usage settings
   before confirming anything. This document is not authorization to incur charges.
3. Set API `CORS_ORIGINS` to a JSON list containing the **exact HTTPS dashboard
   origin**, e.g. `["https://YOUR-DASHBOARD.onrender.com"]`. No wildcard.
4. Set static-site `NEXT_PUBLIC_API_BASE_URL` to the HTTPS API origin before building.
   Rebuild the static site when that URL changes. Never embed a credential there.
5. API `PUBLIC_DEMO=true` and `AI_MODE=mock` are set in the Blueprint. No Gemini,
   n8n, operator login or DB password is needed for this frozen public read model.
   Do not attach the local `.env` or private storage volume.
6. Verify `/health` says `mode=public_demo`, `database=not_used`; `/api/v1/config`
   says read-only. An anonymous POST to `/api/v1/vendors` must return structured
   403 even with operator credentials. Test the public UI and bundled PDF after a
   restart. Do not publish if these checks fail.

The public API listens on Render's `$PORT`. Deep-link route
`/invoices/detail/?id=UUID` uses a static directory index; no dynamic route rewrite
or Node server is required for the exported frontend.

### Neon PostgreSQL preparation

The original Option A named Neon for a database. The hardened public projection
does not need a live DB, so no Neon project is created or billed merely to serve
the portfolio. If a separate **private** development deployment later needs Neon:

- Use a new synthetic-only database; do not connect the public process to local
  operational data. Set backend `DATABASE_URL` to the owner's secret
  `postgresql+psycopg://USER:PASSWORD@HOST/DB?sslmode=require`.
- Use a direct connection for Alembic and scripts that rely on schema/session
  behavior; do not assume a transaction pool preserves session state.
- Run `alembic upgrade head`, then synthetic seeding from a private maintenance
  context. Keep DB credentials server-side. Do not enable public mutations to seed.
- Writable deployment also needs durable private document storage and an access
  gateway. Render Free ephemeral storage is not acceptable for confidential uploads.
- This optional Neon connection/migration is **not tested against a cloud account**.

### Free-plan limitations and terms

Official documentation was consulted on 14 November 2026:

- [Render Free](https://render.com/docs/free): Free web services spin down after
  15 minutes without inbound traffic and may take about a minute to wake. Files
  written at runtime are lost on restart/redeploy/spin-down. The workspace has 750
  free instance hours/month; bandwidth and pipeline-minute quotas also apply.
  Static sites count toward bandwidth/build usage. Exceeding quotas can suspend
  services or trigger supplementary billing where a payment method is configured.
  Render advises against Free services for production applications.
- [Blueprint reference](https://render.com/docs/blueprint-spec) documents the Docker
  context, health route, static publish directory and environment fields used here.
- [Neon plans](https://neon.com/docs/introduction/plans): the consulted Free page
  listed 1 GB Postgres storage/project, 100 CU-hours/project, and scale-to-zero
  after five idle minutes that cannot be disabled. Recheck the live page and
  account console before selecting a plan; limits and eligibility can change.

These are portfolio/development options, not an availability guarantee or a legal
opinion about commercial usage. Check current service terms/acceptable-use rules
and account eligibility before commercial work. No paid Vercel plan is required;
the frontend exports static assets. No live pricing or provider-cost benchmark is
claimed by this project.

## Local public-mode verification

```powershell
docker compose -f infrastructure/compose.public.yml up -d --build
```

Open http://localhost:3002 (API port 8002). This separate project has no database,
upload mount, n8n dependency, operator credential or Gemini key. Do not run it while
the public browser tests own those same ports. Stop it with the same Compose file
and `down`; it does not affect the root private project.

## Option B: one private Linux VM

Use the root Compose file plus `infrastructure/compose.vm.yml`. DNS records must
point to your VM, and ports 80/443 must be reachable for Caddy's HTTPS certificates.
Set `DASHBOARD_DOMAIN`, `API_DOMAIN`, `N8N_DOMAIN`, API `CORS_ORIGINS`, and the
frontend's HTTPS `NEXT_PUBLIC_API_BASE_URL` in private configuration. Rebuild the
frontend. Put a VPN or access gateway in front of the writable demonstration.

```sh
docker compose -f docker-compose.yml -f infrastructure/compose.vm.yml --profile dashboard --profile automation up -d --build
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.seed
```

The optional n8n profile can remain stopped when not being demonstrated; its proxy
route will be unavailable. Bind database/API direct ports to loopback as the root
configuration does, and firewall ports 5433/8000/5678 from the Internet. Caddy
proxies only the named hosts and persists certificates in named volumes. Private
invoice data belongs on a durable volume, not inside the container image.

The VM/Caddy/DNS/TLS path is configuration preparation only; no VM was provisioned
and no certificate was requested. For a publicly reachable portfolio, use the
read-only configuration instead of routing visitors to the operator stack.

## Backup, retention and reset

- Back up the private PostgreSQL DB with `pg_dump` and the invoice volume together;
  encrypt and restrict backups. Preserve n8n's volume/encryption key if used.
- Do not delete or rewrite financial audit/review/ledger rows for retention cleanup.
  Phase 2 run-record retention will be implemented with that feature, not assumed.
- To reset a public demo, restart it: its committed projection is unchanged.
- To reset private sample data, use a **new Compose project and new volumes** with
  separate ports. Do not use `down -v` against the owner's existing demo. Tests and
  benchmarks automatically create/drop only their own random schemas.
- Regenerate the public read model with the QA command below in a private disposable
  execution context, then review its diff and rerun public safety tests before commit.

```sh
docker compose run --rm --no-deps -T -v ./fixtures:/exports backend python -m app.qa public-export --output /exports/public-demo.json
```
