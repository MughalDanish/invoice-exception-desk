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
    parser.add_argument(
        "command", choices=["migrate", "seed", "test", "serve", "worker"]
    )
    parser.add_argument(
        "--once", action="store_true", help="Claim at most one investigation job"
    )
    parser.add_argument(
        "--setup-only",
        action="store_true",
        help="Initialize supported checkpoint tables",
    )
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
            url = url.set(host="127.0.0.1", port=5433)
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
        "test": ["-m", "pytest", "-q", "--tb=short", "-p", "no:cacheprovider"],
        "worker": ["-m", "app.modules.investigation.worker"]
        + (["--once"] if args.once else [])
        + (["--setup-only"] if args.setup_only else []),
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
    if args.command in ("test", "worker"):
        # Tests must never inherit a live provider/key from the operator's .env.
        env["AI_MODE"] = "mock"
        env["INVESTIGATION_MODE"] = "mock"
        env["GEMINI_API_KEY"] = ""
        env["GEMINI_MODEL"] = ""
        # Separate sandbox/elevated runs must not share pytest's Windows ACLs.
        if args.command == "test":
            commands["test"].extend(
                ["--basetemp", tempfile.mkdtemp(prefix="ied-pytest-")]
            )
    return subprocess.run(
        [sys.executable, *commands[args.command]],
        cwd=ROOT / "backend",
        env=env,
        check=False,
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
