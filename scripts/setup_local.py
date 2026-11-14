"""Create ignored local credentials once. Does not print secret values."""

import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    target = ROOT / ".env"
    if target.exists():
        raise SystemExit(".env already exists; keeping existing configuration")
    database_password = secrets.token_urlsafe(24)
    contents = (ROOT / ".env.example").read_text(encoding="utf-8")
    contents = contents.replace(
        "POSTGRES_PASSWORD=CHANGE_ME", f"POSTGRES_PASSWORD={database_password}"
    )
    contents = contents.replace(
        "app:CHANGE_ME@postgres", f"app:{database_password}@postgres"
    )
    contents = contents.replace(
        "AUTH_BOOTSTRAP_PASSWORD=CHANGE_ME",
        f"AUTH_BOOTSTRAP_PASSWORD={secrets.token_urlsafe(24)}",
    )
    contents = contents.replace(
        "N8N_INTEGRATION_KEY=CHANGE_ME",
        f"N8N_INTEGRATION_KEY={secrets.token_urlsafe(32)}",
    )
    contents = contents.replace("AUTH_JWT_SECRET=CHANGE_ME", f"AUTH_JWT_SECRET={secrets.token_urlsafe(48)}")
    with target.open("x", encoding="utf-8") as handle:
        target.chmod(0o600)
        handle.write(contents)
    print(
        "Created ignored .env with generated local credentials. Read it locally to sign in."
    )


if __name__ == "__main__":
    main()
