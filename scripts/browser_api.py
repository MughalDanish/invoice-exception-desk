"""Isolated PostgreSQL API for browser acceptance tests; never resets demo data."""

import os
import re
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import uvicorn
from alembic import command
from alembic.config import Config
from app.core.config import Settings
from app.main import create_app
from app.seed import seed_vendors
from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session


def main():
    values = dotenv_values(ROOT / ".env")
    url = make_url(os.getenv("TEST_DATABASE_URL") or values["DATABASE_URL"])
    if url.host == "postgres":
        url = url.set(host="127.0.0.1", port=5433)
    admin = create_engine(url, connect_args={"connect_timeout": 5})
    marker = ROOT / "storage/browser-test-schema.txt"
    if "--cleanup" in sys.argv:
        if marker.exists():
            schema = marker.read_text().strip()
            if not re.fullmatch(r"ied_browser_[a-f0-9]{32}", schema):
                raise SystemExit("Invalid test schema marker")
            with admin.begin() as connection:
                connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
            marker.unlink()
        admin.dispose()
        return
    schema = "ied_browser_" + uuid.uuid4().hex
    engine = create_engine(
        url, connect_args={"options": f"-csearch_path={schema}", "connect_timeout": 5}
    )
    try:
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        marker.parent.mkdir(exist_ok=True)
        marker.write_text(schema)
        with engine.begin() as connection:
            config = Config(str(ROOT / "backend/alembic.ini"))
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        with Session(engine) as session:
            seed_vendors(session)
        with tempfile.TemporaryDirectory(prefix="ied-browser-") as folder:
            settings = Settings(
                _env_file=None,
                demo_basic_user="browser-operator",
                demo_basic_password="browser-test-password-only",
                n8n_integration_key="browser-test-integration-only",
                ai_mode="mock",
                storage_dir=Path(folder),
                fixtures_dir=ROOT / "fixtures",
                cors_origins=["http://localhost:3001"],
            )
            uvicorn.run(create_app(settings, engine), host="127.0.0.1", port=8001)
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        marker.unlink(missing_ok=True)
        admin.dispose()


if __name__ == "__main__":
    main()
