# Day 11 learning guide — Protocol is not permission

## Follow the request

`serve()` reads one bounded UTF-8 line and parses a JSON-RPC message.
`LocalMCPServer.handle()` validates the envelope and lifecycle, verifies the
existing operator session, then selects an allowlisted method. A tools/call accepts
only a tool name and empty arguments. `OperatorToolHost.call()` rechecks the access
JWT and database session, loads its host-selected invoice, and captures the same
bounded immutable snapshot used by investigation execution. `ReadOnlyTools` receives
only that snapshot and a server-created `ToolRequest`; it receives no database
session, filesystem access or network client. Its typed result becomes MCP text
and structured content.

The adapter pattern translates protocols while preserving the domain boundary.
JSON-RPC IDs correlate replies with requests; notifications have no response.
Initialize negotiates the protocol and capabilities. The initialized notification
then moves the connection into the operational state. We deliberately advertise
only functionality we implement.

## Why the host supplies scope

Tool descriptions and readOnlyHint annotations inform clients; they do not enforce
permissions. Enforcement happens in JWT verification, PostgreSQL session checks,
host-selected invoice scope, strict argument validation and the existing tools.
The current application grants active operators access across invoices; MCP does
not invent a narrower per-user invoice ownership model. The host still fixes one
invoice for the lifetime of the process so model text cannot change its target.

A valid JWT alone is insufficient: logout revokes its backing session immediately.
Repeated authorization ensures a running subprocess cannot keep using an old
session after revocation. Refresh tokens are not accepted as access tokens. Public
demo mode cannot instantiate the authenticated host.

## Maintain components independently

- Add evidence capabilities to the existing domain `ToolName`/`ReadOnlyTools`
  contracts first; the MCP list derives from that allowlist automatically. Do not
  add a separate SQL or HTTP helper inside this adapter.
- Change framing limits in the module constants and retain oversized-frame tests.
- To change protocol support, study the specification and update negotiation and
  lifecycle tests together. Supporting an additional advertised capability requires
  implementing its methods; changing a version string alone is insufficient.
- Keep user-facing errors generic. For diagnostics prefer bounded error types over
  exception strings or source payloads.
- Keep any future secure launcher separate from model-supplied tool arguments.
  Never make a login password, access token or privileged invoice selector a tool
  parameter. Existing financial authorization remains outside MCP.

## Tests and commands

From repository root:

```powershell
.venv/Scripts/python.exe -m pytest backend/tests/test_investigation_mcp.py -q
.venv/Scripts/python.exe scripts/dev.py test --postgres
.venv/Scripts/python.exe -m ruff check --config backend/pyproject.toml backend/app/modules/investigation/mcp_adapter.py backend/tests/test_investigation_mcp.py scripts/run_mcp_stdio.py
```

The first command runs protocol tests and skips integration cases unless the
disposable PostgreSQL configuration is provided. The second runs all regressions
with isolated schemas. Tests prove schema rejection of scope spoofing, SQL, URLs,
paths and write operations; malformed/batch/oversized frames; version negotiation;
and existing operator-session revocation/expiry. No production token is needed.

For a local integration, the trusted host launches `.venv/Scripts/python.exe
scripts/run_mcp_stdio.py` with a current operator access token and selected invoice
in ephemeral launch environment. Standard input/output must contain only MCP
JSON-RPC. Do not manually paste secret-bearing launch commands. The current
repository does not include a browser-to-process credential broker.

## Exercise

Extend the unit test's in-memory host to mark a session revoked immediately after
initialization. Predict tools/list and tools/call results before running the test.
Then explain why readOnlyHint cannot replace authorization, why putting invoice_id
in model-controlled arguments widens the trust boundary, and why sending a raw
exception message could disclose financial evidence even when a tool is read-only.
