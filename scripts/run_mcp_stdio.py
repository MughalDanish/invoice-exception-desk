"""Trusted local host launcher; stdout contains MCP JSON-RPC only.

The host supplies a current operator access token and authorized invoice UUID in
ephemeral launch environment. Do not paste tokens into command history or files.
No token refresh is implemented: restart with a current session after expiry.
"""

import os
import sys
import uuid
from pathlib import Path

from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import Settings
from app.db.session import build_engine, build_session_factory
from app.modules.investigation.mcp_adapter import (
    LocalMCPServer,
    OperatorToolHost,
    serve,
)


def main():
    engine = None
    try:
        token = os.environ.pop("IED_MCP_ACCESS_TOKEN", "")
        invoice_id = uuid.UUID(os.environ.pop("IED_MCP_INVOICE_ID", ""))
        settings = Settings(_env_file=ROOT / ".env")
        url = make_url(settings.database_url)
        if url.host == "postgres":
            settings.database_url = url.set(
                host="127.0.0.1", port=5433
            ).render_as_string(hide_password=False)
        engine = build_engine(settings.database_url)
        host = OperatorToolHost(
            settings, build_session_factory(engine), token, invoice_id
        )
        host.authorize()
        serve(LocalMCPServer(host), sys.stdin.buffer, sys.stdout.buffer)
        return 0
    except Exception:  # noqa: BLE001 - Never expose startup credentials through exception text.
        sys.stderr.write(
            "Local MCP startup failed; check private operator session and scope.\n"
        )
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
