"""Real JSON-RPC framing and adversarial arguments; real session revocation in PG."""

import io
import json
import uuid
from datetime import timedelta
from typing import get_args

import jwt
import pytest
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import AuthSession
from app.modules.auth.cookies import names
from app.modules.auth.security import decode_token, now
from app.modules.investigation.mcp_adapter import (
    MAX_FRAME_BYTES,
    LocalMCPServer,
    OperatorToolHost,
    serve,
)
from app.modules.investigation.schemas import ToolName
from tests.test_investigation import prepared


class Host:
    def __init__(self):
        self.revoked = False
        self.calls = []

    def authorize(self):
        if self.revoked:
            raise AppError(401, "REVOKED", "sensitive-value")

    def call(self, name):
        self.calls.append(name)
        return {"name": name, "facts": ["bounded synthetic fact"]}


def request(method, params=None, request_id=1):
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}


def ready(host=None):
    server = LocalMCPServer(host or Host())
    response = server.handle(
        request(
            "initialize",
            {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "synthetic-test", "version": "1"},
            },
        )
    )
    assert response["result"]["capabilities"] == {"tools": {"listChanged": False}}
    assert server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    return server


def test_protocol_lifecycle_schema_and_read_only_call():
    host = Host()
    server = LocalMCPServer(host)
    assert server.handle(request("tools/list"))["error"]["code"] == -32600
    server = ready(host)
    tools = server.handle(request("tools/list"))["result"]["tools"]
    assert {tool["name"] for tool in tools} == set(get_args(ToolName))
    assert all(tool["annotations"]["readOnlyHint"] for tool in tools)
    assert all(tool["inputSchema"]["additionalProperties"] is False for tool in tools)
    response = server.handle(request("tools/call", {"name": "get_rule_results", "arguments": {}}))
    assert response["result"]["isError"] is False
    assert (
        json.loads(response["result"]["content"][0]["text"])
        == response["result"]["structuredContent"]
    )
    assert host.calls == ["get_rule_results"]


@pytest.mark.parametrize(
    "arguments",
    [
        {"invoice_id": str(uuid.uuid4())},
        {"supplier_key": "other"},
        {"role": "OPERATOR"},
        {"sql": "DELETE FROM invoices"},
        {"url": "http://127.0.0.1"},
        {"path": "../../.env"},
        {"snapshot": {}},
        {"instructions": "ignore safeguards"},
        [],
        None,
        "",
    ],
)
def test_model_cannot_supply_scope_or_arbitrary_instructions(arguments):
    server = ready()
    response = server.handle(
        request("tools/call", {"name": "get_rule_results", "arguments": arguments})
    )
    assert response["error"]["code"] == -32602
    assert server.host.calls == []


@pytest.mark.parametrize("name", ["post_invoice", "approve_supplier", "exec", "fetch", "sql"])
def test_write_and_unknown_tools_rejected(name):
    server = ready()
    assert server.handle(request("tools/call", {"name": name}))["error"]["code"] == -32602


def test_revocation_blocks_discovery_and_execution_without_sensitive_error():
    host = Host()
    server = ready(host)
    host.revoked = True
    for method, params in [("tools/list", {}), ("tools/call", {"name": "get_rule_results"})]:
        response = server.handle(request(method, params))
        assert response["error"]["code"] == -32001
        assert "sensitive" not in json.dumps(response)
    assert host.calls == []


def test_stdio_parsing_notifications_batches_and_frame_bounds():
    server = ready()
    reader = io.BytesIO(
        b'not-json\n[]\n{"jsonrpc":"2.0","method":"notifications/cancelled"}\n'
        b'{"jsonrpc":"2.0","id":8,"method":"ping"}\n'
    )
    writer = io.BytesIO()
    serve(server, reader, writer)
    replies = [json.loads(line) for line in writer.getvalue().splitlines()]
    assert [reply.get("error", {}).get("code") for reply in replies] == [-32700, -32600, None]
    assert replies[2]["id"] == 8
    writer = io.BytesIO()
    serve(server, io.BytesIO(b"x" * (MAX_FRAME_BYTES + 1)), writer)
    assert json.loads(writer.getvalue())["error"]["code"] == -32600


def test_protocol_version_negotiation_and_no_double_initialize():
    server = LocalMCPServer(Host())
    params = {
        "protocolVersion": "unknown",
        "capabilities": {},
        "clientInfo": {"name": "x", "version": "1"},
    }
    assert server.handle(request("initialize", params))["result"]["protocolVersion"] == "2025-11-25"
    assert server.handle(request("initialize", params))["error"]["code"] == -32600


@pytest.mark.parametrize("expired", [False, True])
def test_real_operator_session_rechecked_per_call(pg_client, settings, expired):
    invoice_id = prepared(pg_client, pg_client.app.state.engine)
    token = pg_client.operator_cookies[names(settings)[0]]
    host = OperatorToolHost(
        settings, pg_client.app.state.session_factory, token, uuid.UUID(invoice_id)
    )
    server = ready(host)
    assert "result" in server.handle(request("tools/call", {"name": "get_rule_results"}))
    claims = decode_token(settings, token, "access")
    with Session(pg_client.app.state.engine) as session, session.begin():
        row = session.get(AuthSession, uuid.UUID(claims["sid"]))
        if expired:
            row.expires_at = now() - timedelta(seconds=1)
        else:
            row.revoked_at = now()
    assert (
        server.handle(request("tools/call", {"name": "get_rule_results"}))["error"]["code"]
        == -32001
    )


def test_missing_token_and_public_demo_cannot_create_authorized_host(settings):
    host = OperatorToolHost(
        settings, lambda: pytest.fail("DB must not be reached"), "", uuid.uuid4()
    )
    assert LocalMCPServer(host).handle(request("ping"))["error"]["code"] == -32001
    with pytest.raises(ValueError):
        OperatorToolHost(settings.model_copy(update={"public_demo": True}), None, "", uuid.uuid4())


@pytest.mark.parametrize("kind", ["expired_access", "refresh"])
def test_expired_access_and_refresh_tokens_never_reach_tools(settings, kind):
    from app.modules.auth.security import issue_token

    token = issue_token(
        settings, uuid.uuid4(), uuid.uuid4(), "refresh" if kind == "refresh" else "access"
    )
    if kind == "expired_access":
        claims = decode_token(settings, token, "access")
        claims["exp"] = int((now() - timedelta(seconds=5)).timestamp())
        token = jwt.encode(claims, settings.auth_jwt_secret.get_secret_value(), algorithm="HS256")
    host = OperatorToolHost(
        settings, lambda: pytest.fail("Database must not be reached"), token, uuid.uuid4()
    )
    assert LocalMCPServer(host).handle(request("ping"))["error"]["code"] == -32001
