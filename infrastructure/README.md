# Infrastructure

The root Compose project is the private operator stack: PostgreSQL, FastAPI,
optional dashboard and optional n8n. Ports bind to loopback. Database and source
files use named volumes. Run migrations before seeding/using the private API.

- `compose.public.yml`: isolated local public preview, bundled synthetic projection,
  ports 3002/8002, no database, credentials, n8n or upload mount.
- `../render.yaml`: public API + Next static export Blueprint preparation.
- `compose.vm.yml` + `Caddyfile`: private Linux VM proxy/HTTPS preparation over the
  original operator stack. Keep it behind a VPN/access gateway.

Read [deployment.md](../docs/deployment.md) for exact commands, required variables,
Neon guidance, free-plan limitations, reset/backup policy and verification limits.
No cloud resources or certificates have been provisioned.
