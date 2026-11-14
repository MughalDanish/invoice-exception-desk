import os
import uuid
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from alembic import command
from app.core.config import Settings
from app.main import create_app

ROOT = Path(__file__).resolve().parents[2]
AUTH = ("operator", "test-password-only")


@pytest.fixture
def settings(tmp_path):
    return Settings(
        _env_file=None,
        auth_jwt_secret="test-signing-secret-at-least-32-bytes-long",
        auth_cookie_secure=False,
        auth_bootstrap_username=AUTH[0],
        auth_bootstrap_password=AUTH[1],
        storage_dir=tmp_path / "uploads",
        fixtures_dir=ROOT / "fixtures",
        ai_mode="mock",
        gemini_api_key="",
        gemini_model="",
    )


@pytest.fixture
def client(settings):
    # Engine is lazy: authentication, format rejection, and docs do not need a DB.
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture
def clean_pdf():
    return (ROOT / "fixtures" / "invoices" / "clean-001.pdf").read_bytes()


@pytest.fixture
def pg_engine():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to run PostgreSQL integration tests")
    # No test drops existing tables. Each runs in its own random, isolated schema.
    schema = "ied_test_" + uuid.uuid4().hex
    admin = create_engine(url, connect_args={"connect_timeout": 5})
    engine = create_engine(
        url,
        connect_args={
            "connect_timeout": 5,
            "options": f"-csearch_path={schema}",
        },
    )
    try:
        with admin.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        with engine.begin() as connection:
            config = Config(str(ROOT / "backend" / "alembic.ini"))
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture
def pg_client(settings, pg_engine):
    from sqlalchemy.orm import Session

    from app.modules.auth.bootstrap import bootstrap_operator

    with Session(pg_engine) as db:
        bootstrap_operator(db, *AUTH)
    app = create_app(settings, engine=pg_engine)
    with TestClient(app) as operator:
        nonce = operator.get("/api/v1/auth/csrf").json()["csrf_token"]
        result = operator.post(
            "/api/v1/auth/login",
            json={"username": AUTH[0], "password": AUTH[1]},
            headers={"X-CSRF-Token": nonce},
        )
        assert result.status_code == 200, result.text
        cookies = dict(operator.cookies)
        nonce = result.json()["csrf_token"]
    with TestClient(app) as test_client:
        test_client.operator_cookies = cookies
        test_client.headers["X-CSRF-Token"] = nonce
        yield test_client


def operator_auth(client):
    return {"cookies": getattr(client, "operator_cookies", {})}


@pytest.fixture
def authenticated_client(settings):
    from app.core.auth import require_operator

    app = create_app(settings)
    app.dependency_overrides[require_operator] = lambda: AUTH[0]
    with TestClient(app) as client:
        yield client
