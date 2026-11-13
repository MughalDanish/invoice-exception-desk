# Optional local intake automation

Import `workflows/invoice-intake.json` into **n8n 2.46.6**. The workflow is inactive
and contains no secrets. Direct dashboard upload works with n8n stopped.
FastAPI owns extraction/validation; this workflow never approves or posts invoices.

## Start and import

```powershell
docker compose --profile automation up -d n8n
docker compose exec -T n8n n8n import:workflow --input=/workflows/invoice-intake.json
```

Open http://localhost:5678 and create your local n8n owner account. This instance
uses its own named volume, publishes loopback only, and does not affect another
n8n installation. Keep n8n's generated encryption key/configuration with that volume.
The HTTP-only cookie setting is strictly for this local loopback environment.

In the editor, open **Invoice Desk - authenticated intake** and configure:

1. **Fixture webhook**: create Header Auth credentials with header
   `X-Webhook-Key` and a new local random value. This protects intake into n8n.
   Keep it distinct from the backend integration key. Select these credentials.
2. **Backend intake**: select Generic Credential Type → Header Auth. Create
   credentials named `Invoice Desk backend key`, header `X-Integration-Key`, value
   copied privately from root `.env` → `N8N_INTEGRATION_KEY`. The smoke helper below
   can import this encrypted credential automatically; select it in the editor.
3. Keep the URL `http://backend:8000/api/v1/integrations/n8n/invoices` inside Compose.
   For an external n8n instance, configure its privately reachable backend URL.

Click **Listen for test event** on the webhook. Send a multipart POST using its
shown test URL, a single field `file`, header `X-Webhook-Key`, and header
`X-Delivery-Id: demo-message-001`. Use a supplied fixture PDF. For example, use
curl.exe with your header credential supplied locally (never commit its value):

```powershell
curl.exe -X POST http://localhost:5678/webhook-test/invoice-intake -H "X-Webhook-Key: YOUR_LOCAL_WEBHOOK_KEY" -H "X-Delivery-Id: demo-message-001" -F "file=@fixtures/invoices/clean-004.pdf;type=application/pdf"
```

The webhook acknowledges receipt immediately; this is **not proof of processing
success**. Inspect the live execution's Safe result node and the dashboard for the
backend's authoritative invoice state. Failed executions show a sanitized failure.
Production webhook URLs work only after publishing/activating in your local n8n.

The guard accepts exactly one PDF/JPG/PNG with a supported extension and MIME,
actual bytes from 1 to 8 MiB, and a stable safe delivery ID. It intentionally
rejects multiple attachments/items rather than silently dropping extras. Split
multi-attachment email intake into separate executions before extending the MVP.
The backend independently validates signatures, parses files, and enforces its size
limit. n8n's guard is not a substitute for backend validation.

## Idempotency, retries and status

Delivery keys are `{message-id}:attachment-0`. Keep the same message ID on retry;
different attachments must have different message IDs/indexes. Backend receipts
store hashed keys and bind them to file SHA-256 and invoice ID. The same key and
bytes return the original ID; changed bytes with the same key return 409. Global
file deduplication also works across dashboard and integration sources.

The HTTP node retries at most three attempts, two seconds apart, with a 60-second
request timeout; the workflow ceiling is 240 seconds. Fix configuration/auth/4xx
errors before manually retrying with the same delivery identity. There is no loop.
Concurrent extraction can return 202/EXTRACTING; check the dashboard and retry the
delivery later. Completed review/terminal data is preserved. Failed extraction is
not repeatedly retried by email delivery; the authenticated operator explicitly
retries through the dashboard. No integration credential grants list, source-file,
correction, approval or ledger access.

Execution input/output persistence is disabled (including manual execution saving)
to avoid retaining attachments/PII in n8n history. During an open manual run, n8n
still displays node data; use synthetic fixtures only. The error branch logs a
generic `INVOICE_INTEGRATION_FAILED` message and fails the execution. Use server
logs/dashboard status for troubleshooting; no raw provider errors or attachments
are forwarded to notifications. This MVP does not implement a separate error
workflow or automated failure-notification service.

## Optional Gmail / Telegram (unverified without credentials)

Gmail AP-DEMO is disabled. After creating Gmail OAuth credentials, select the
actual `AP-DEMO` label ID, enable attachment downloading and disable the webhook
trigger if desired. Keep the single-attachment restriction. Gmail's `id` supplies
the stable delivery ID. Sender filtering may narrow intake but never approves a
supplier. Gmail OAuth polling has not been tested against an account.

Optional Telegram alert is disabled. Attach your Telegram credential and replace
the local chat ID before enabling it. Only invoice ID, state and blocker codes
from Safe result are sent. No supplier, email body, amounts or document bytes.
The Needs review branch only notifies; all decisions remain in the dashboard.
Telegram has not been tested against a bot/account.

## Credential-free external accounts smoke test

With backend/mock mode and local n8n running:

```powershell
.\.venv\Scripts\python.exe scripts/n8n_smoke.py
```

This imports the backend Header Auth credential privately over stdin into encrypted
n8n storage, and a test-only workflow named **Invoice Desk CLI smoke**. It replaces
the triggers with a manual synthetic fixture, reuses the exported guard/HTTP/result
nodes, executes twice and checks the same backend invoice ID. It writes no ledger
entry and requires no Gmail/Telegram account. The synthetic clean-004 invoice remains
in the demo database. CLI output/errors are kept private in ignored storage; the
helper prints pass/fail only. The CLI smoke does not verify live webhook/Gmail OAuth
or Telegram delivery. Select its imported backend credential for the main workflow.

Regenerate the versioned JSON with `python n8n/build_workflow.py`.
Reference: [n8n HTTP Request configuration](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.httprequest/).
