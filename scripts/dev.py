"""Run host-side backend commands with root .env and localhost DB settings."""

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["migrate", "seed", "test", "serve"])
    parser.add_argument(
        "--all", action="store_true", help="Seed every synthetic fixture"
    )
    parser.add_argument(
        "--postgres", action="store_true", help="Include PostgreSQL integration tests"
    )
    args = parser.parse_args()
    env = os.environ.copy()
    for key, value in dotenv_values(ROOT / ".env").items():
        if value is not None:
            env.setdefault(key, value)
    raw_url = env.get("DATABASE_URL", "")
    if raw_url:
        url = make_url(raw_url)
        if url.host == "postgres":
            url = url.set(host="localhost", port=5433)
        env["DATABASE_URL"] = url.render_as_string(hide_password=False)
    env["STORAGE_DIR"] = str(ROOT / "storage" / "uploads")
    env["FIXTURES_DIR"] = str(ROOT / "fixtures")
    if args.postgres:
        if not raw_url:
            raise SystemExit("Create .env first with scripts/setup_local.py")
        env["TEST_DATABASE_URL"] = env["DATABASE_URL"]
    commands = {
        "migrate": ["-m", "alembic", "upgrade", "head"],
        "seed": ["-m", "app.seed"] + (["--all"] if args.all else []),
        "test": ["-m", "pytest", "-q", "-p", "no:cacheprovider"],
        "serve": [
            "-m",
            "uvicorn",
            "app.main:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ],
    }
    if args.command == "test":
        # Separate sandbox/elevated runs must not share pytest's Windows ACLs.
        commands["test"].extend(["--basetemp", tempfile.mkdtemp(prefix="ied-pytest-")])
    return subprocess.run(
        [sys.executable, *commands[args.command]],
        cwd=ROOT / "backend",
        env=env,
        check=False,
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
