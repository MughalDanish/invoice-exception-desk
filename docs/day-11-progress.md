# Day 11 — Local read-only MCP adapter

## Delivered

The optional local MCP stretch milestone now has an actual newline-framed UTF-8
JSON-RPC stdio server. It negotiates protocol `2025-11-25`, advertises only tools,
requires initialize/initialized before tool discovery or invocation, and supports
ping. It does not start a public HTTP listener or install another dependency.

Tool names come from the existing `ToolName` contract. Descriptions advertise
read-only, non-destructive behavior. Their input schema accepts an empty object:
the trusted host fixes the invoice and the backend derives supplier scope. A
model cannot pass another invoice, role, snapshot, SQL, URL, path or write action.
Calls delegate to the same strict `ToolRequest` and `ReadOnlyTools` implementation
used by investigations; no alternative financial authority exists.

`OperatorToolHost` verifies the existing access JWT and PostgreSQL-backed operator
session on every request, and again immediately before capturing current evidence.
Expired, revoked, inactive or non-operator sessions fail closed. Public demo mode
cannot construct this host. Calls capture the current eligible invoice from the
database rather than trusting a caller-supplied snapshot.

Frames are bounded to 16 KiB, results to 64 KiB; malformed JSON, batches, unsupported
methods and unsafe arguments are rejected. Notifications do not produce normal
responses. Exceptions return sanitized messages, never SQL, credentials or invoice
payloads. Oversized input closes the transport after one safe error response.

## Files

- `backend/app/modules/investigation/mcp_adapter.py`: scoped authenticated host,
  lifecycle, tool discovery/calls and framing.
- `scripts/run_mcp_stdio.py`: local trusted-host process entrypoint.
- `backend/tests/test_investigation_mcp.py`: protocol and security regression cases.
- `docs/learning-day-11.md`: maintenance guide and exercise.

## Verification performed by the Day 11 agent

Focused unit run: **23 passed, 2 PostgreSQL cases skipped** because that direct
command did not set `TEST_DATABASE_URL`. The two integration cases exercise real
operator-session expiry/revocation after a successful read; they must pass in the
root agent's integrated PostgreSQL run before declaring overall verification.

Final integration: the complete PostgreSQL suite passed **340 tests with no skips**,
including all **25 MCP cases** and both real session expiry/revocation tests.
See [combined results](days-9-12-progress.md) for exact command/results and warnings.

Ruff lint and formatting passed for these files. No live provider, live invoice,
Slack message, persistent workflow or financial action was invoked. Broader
integration/regression results belong in the combined Day 9–12 report.

## Limits and operational boundaries

This is a deliberately small MCP protocol implementation, not an assertion of
full SDK conformance. It exposes no resources/prompts, streaming HTTP, sampling,
pagination, remote authentication, automatic refresh or public listener. Protocol
versions other than the supported one receive the supported version as negotiation;
clients must disconnect if they cannot support it.

The launcher needs a trusted host to provide `IED_MCP_ACCESS_TOKEN` and
`IED_MCP_INVOICE_ID` in an ephemeral process environment. It immediately removes
those variables from its own environment and does not persist them, but a local
process inspector may still access process secrets. Do not paste tokens into
shell commands/history, `.env`, source control or logs. A browser/agent UI that
securely brokers this launch is not included. Existing browser HttpOnly cookies
remain unchanged. Restart with a current existing session after access expiry;
this adapter does not independently mint credentials or refresh a session.

On Windows host execution, the launcher maps the compose database hostname to
the existing localhost PostgreSQL port, matching `scripts/dev.py`. It closes its
engine on EOF or startup failure. No database migration was required for MCP.

Specification references:
[stdio transport](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports),
[lifecycle](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle),
[tools](https://modelcontextprotocol.io/specification/2025-11-25/server/tools).
