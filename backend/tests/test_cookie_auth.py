import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import AuthSession, AuthUser
from app.modules.auth.security import decode_token, digest, issue_token
from tests.conftest import AUTH


def login(client):
    token = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    result = client.post(
        "/api/v1/auth/login",
        json={"username": AUTH[0], "password": AUTH[1]},
        headers={"X-CSRF-Token": token},
    )
    assert result.status_code == 200
    client.headers["X-CSRF-Token"] = result.json()["csrf_token"]
    return result


def test_cookie_lifetime_hash_and_current_user(pg_client, pg_engine, settings):
    result = login(pg_client)
    cookies = result.headers.get_list("set-cookie")
    assert all("HttpOnly" in c and "SameSite=lax" in c for c in cookies)
    assert "Max-Age=86400" in cookies[0]
    assert "Max-Age=604800" in cookies[1] and "Path=/api/v1/auth" in cookies[1]
    assert set(result.json()) == {"user", "csrf_token"}
    access = decode_token(settings, pg_client.cookies["ied_access"], "access")
    refresh = decode_token(settings, pg_client.cookies["ied_refresh"], "refresh")
    assert access["exp"] - access["iat"] == 86400
    assert refresh["exp"] - refresh["iat"] == 604800
    with Session(pg_engine) as db:
        assert db.scalar(select(AuthUser)).password_hash.startswith("$argon2id$")
        row = db.get(AuthSession, uuid.UUID(refresh["sid"]))
        assert row.refresh_hash == digest(pg_client.cookies["ied_refresh"])
    assert pg_client.get("/api/v1/auth/me").json()["username"] == AUTH[0]


def test_rotation_reuse_revokes_entire_session(pg_client):
    login(pg_client)
    old = dict(pg_client.cookies)
    assert pg_client.post("/api/v1/auth/refresh").status_code == 200
    assert pg_client.cookies["ied_refresh"] != old["ied_refresh"]
    latest = dict(pg_client.cookies)
    pg_client.cookies.clear()
    pg_client.cookies.update(old)
    assert pg_client.post("/api/v1/auth/refresh").json()["error"]["code"] == "REFRESH_REUSED"
    pg_client.cookies.update(latest)
    assert pg_client.get("/api/v1/auth/me").status_code == 401
    assert pg_client.post("/api/v1/auth/refresh").status_code == 401


def test_logout_revokes_copied_access_and_refresh(pg_client):
    login(pg_client)
    saved = dict(pg_client.cookies)
    assert pg_client.post("/api/v1/auth/logout").status_code == 204
    pg_client.cookies.update(saved)
    assert pg_client.get("/api/v1/auth/me").status_code == 401
    assert pg_client.post("/api/v1/auth/refresh").status_code == 401


def test_csrf_and_origin_guard(pg_client):
    assert (
        pg_client.post(
            "/api/v1/auth/login", json={"username": AUTH[0], "password": AUTH[1]}
        ).status_code
        == 403
    )
    login(pg_client)
    assert (
        pg_client.post(
            "/api/v1/auth/refresh", headers={"Origin": "https://evil.example"}
        ).status_code
        == 403
    )
    assert (
        pg_client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": "forged"}).status_code == 403
    )
    assert pg_client.get("/api/v1/auth/me").status_code == 200


def test_wrong_password_and_basic_not_supported(pg_client):
    nonce = pg_client.get("/api/v1/auth/csrf").json()["csrf_token"]
    assert (
        pg_client.post(
            "/api/v1/auth/login",
            json={"username": AUTH[0], "password": "wrong"},
            headers={"X-CSRF-Token": nonce},
        ).status_code
        == 401
    )
    assert pg_client.get("/api/v1/invoices", auth=AUTH).status_code == 401


def test_token_signature_and_purpose(settings):
    token = issue_token(settings, uuid.uuid4(), uuid.uuid4(), "refresh")
    with pytest.raises(AppError):
        decode_token(settings, token, "access")
    with pytest.raises(AppError):
        decode_token(settings, token[:-10] + "abcdefghij", "refresh")
