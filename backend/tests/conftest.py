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
        demo_basic_user=AUTH[0],
        demo_basic_password=AUTH[1],
        storage_dir=tmp_path / "uploads",
        fixtures_dir=ROOT / "fixtures",
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
    with TestClient(create_app(settings, engine=pg_engine)) as test_client:
        yield test_client
