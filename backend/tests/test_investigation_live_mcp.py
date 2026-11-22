"""Actual official MCP client and isolated PostgreSQL delegation boundary."""

import sys
import time
import uuid
from datetime import timedelta
from types import SimpleNamespace

import jwt
import pytest
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import AuthSession, InvestigationRun
from app.modules.auth.security import decode_token, now
from app.modules.investigation.delegation import (
    AUDIENCE,
    ISSUER,
    RunToolHost,
    assert_run_authorized,
    issue_capability,
)
from app.modules.investigation.mcp_client import MCPClient, MCPUnavailable, subprocess_environment
from app.modules.investigation.queue import claim_next
from tests.test_investigation import financial_state, prepared
from tests.test_investigation_durable import enqueue


def bound_run(client, engine, settings):
    identifier = prepared(client, engine)
    run_id, _ = enqueue(client, identifier, key="mcp-live-" + uuid.uuid4().hex)
    with Session(engine) as session, session.begin():
        auth = session.scalar(select(AuthSession).where(AuthSession.revoked_at.is_(None)))
        row = session.get(InvestigationRun, run_id)
        row.requested_user_id, row.requested_session_id = auth.user_id, auth.id
        # Claim using established mock version; this test exercises delegated
        # transport independently of provider/worker routing.
    claim = claim_next(client.app.state.session_factory, "mcp-test", run_id=run_id)
    with engine.connect() as connection:
        schema = connection.scalar(text("SELECT current_schema()"))
    url = make_url(engine.url).update_query_dict({"options": f"-csearch_path={schema}"})
    configured = settings.model_copy(
        update={"database_url": url.render_as_string(hide_password=False)}
    )
    return configured, claim


def test_actual_stdio_client_negotiates_and_reads_frozen_facts(pg_client, pg_engine, settings):
    settings, claim = bound_run(pg_client, pg_engine, settings)
    before = financial_state(pg_engine)
    with MCPClient(settings, pg_client.app.state.session_factory, claim) as client:
        assert len(client.definitions) == 7
        rules = client.call("get_rule_results")
        assert rules.data["rules"] and rules.data["currency"] == "USD"
        policy = client.call("get_supplier_policy")
        assert "policy" in policy.data
        with pytest.raises(MCPUnavailable):
            client.call("get_rule_results", {"invoice_id": str(uuid.uuid4())})
    assert not client._thread.is_alive()
    assert financial_state(pg_engine) == before


def test_capability_is_not_a_browser_token_and_revocation_is_immediate(
    pg_client, pg_engine, settings
):
    settings, claim = bound_run(pg_client, pg_engine, settings)
    factory = pg_client.app.state.session_factory
    token = issue_capability(settings, factory, claim)
    with pytest.raises(AppError):
        decode_token(settings, token, "access")
    host = RunToolHost(settings, factory, token)
    assert host.call("get_rule_results")["data"]["rules"]
    with Session(pg_engine) as session, session.begin():
        row = session.get(InvestigationRun, claim.run_id)
        session.get(AuthSession, row.requested_session_id).revoked_at = now()
    with pytest.raises(AppError):
        host.call("get_rule_results")
    with pytest.raises(AppError):
        assert_run_authorized(settings, factory, claim)


@pytest.mark.parametrize("change", ["aud", "type", "exp", "fence", "iid", "digest"])
def test_signed_but_wrong_capability_binding_is_rejected(pg_client, pg_engine, settings, change):
    settings, claim = bound_run(pg_client, pg_engine, settings)
    factory = pg_client.app.state.session_factory
    token = issue_capability(settings, factory, claim)
    claims = jwt.decode(
        token,
        settings.auth_jwt_secret.get_secret_value(),
        algorithms=["HS256"],
        audience=AUDIENCE,
        issuer=ISSUER,
    )
    claims[change] = {
        "aud": "browser",
        "type": "access",
        "exp": (now() - timedelta(seconds=1)).timestamp(),
        "fence": claim.fence + 1,
        "iid": str(uuid.uuid4()),
        "digest": "0" * 64,
    }[change]
    altered = jwt.encode(claims, settings.auth_jwt_secret.get_secret_value(), algorithm="HS256")
    with pytest.raises(AppError):
        RunToolHost(settings, factory, altered)


def test_cancel_and_stale_fence_stop_existing_child(pg_client, pg_engine, settings):
    settings, claim = bound_run(pg_client, pg_engine, settings)
    factory = pg_client.app.state.session_factory
    with MCPClient(settings, factory, claim) as client:
        assert client.call("get_rule_results").status == "FOUND"
        with Session(pg_engine) as session, session.begin():
            row = session.get(InvestigationRun, claim.run_id)
            row.cancel_requested = True
            row.fence += 1
        with pytest.raises(AppError):
            client.call("get_rule_results")
    assert not client._thread.is_alive()


def test_subprocess_environment_never_inherits_model_or_integration_secrets(settings, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "must-not-cross-boundary")
    monkeypatch.setenv("N8N_INTEGRATION_KEY", "must-not-cross-boundary")
    monkeypatch.setenv("IED_MCP_ACCESS_TOKEN", "must-not-cross-boundary")
    env = subprocess_environment(settings, "synthetic-capability")
    assert not {"GEMINI_API_KEY", "N8N_INTEGRATION_KEY", "IED_MCP_ACCESS_TOKEN"} & set(env)
    assert env["IED_MCP_CAPABILITY"] == "synthetic-capability"
    assert env["DATABASE_URL"] == settings.database_url


def test_server_cannot_expand_advertised_tool_surface():
    tools = SimpleNamespace(tools=[], nextCursor=None)
    with pytest.raises(MCPUnavailable):
        MCPClient._validate_definitions(tools)


@pytest.mark.parametrize("program", ["raise SystemExit(1)", "import time; time.sleep(60)"])
def test_real_child_crash_or_hang_has_bounded_cleanup(
    pg_client, pg_engine, settings, monkeypatch, program
):
    import mcp

    settings, claim = bound_run(pg_client, pg_engine, settings)
    parameters = mcp.StdioServerParameters

    def failing_child(**kwargs):
        return parameters(command=sys.executable, args=["-c", program], env=kwargs["env"])

    monkeypatch.setattr(mcp, "StdioServerParameters", failing_child)
    client = MCPClient(
        settings, pg_client.app.state.session_factory, claim, timeout=0.3, startup_timeout=0.3
    )
    started = time.monotonic()
    with pytest.raises(MCPUnavailable):
        with client:
            pytest.fail("Broken MCP must never expose tool definitions")
    assert time.monotonic() - started < 9
    assert not client._thread.is_alive()
