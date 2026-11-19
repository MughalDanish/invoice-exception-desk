"""In-image stdio child. No dotenv loading, browser tokens or model credentials."""

import os
import sys

from app.core.config import Settings
from app.db.session import build_engine, build_session_factory
from app.modules.investigation.delegation import RunToolHost
from app.modules.investigation.mcp_adapter import LocalMCPServer, serve


def main():
    engine = None
    try:
        capability = os.environ.pop("IED_MCP_CAPABILITY", "")
        settings = Settings(_env_file=None)
        engine = build_engine(settings.database_url)
        host = RunToolHost(settings, build_session_factory(engine), capability)
        serve(LocalMCPServer(host), sys.stdin.buffer, sys.stdout.buffer)
    except Exception:  # noqa: BLE001
        # stderr may be captured by SDK: no raw exception/SQL/payload/credential text.
        sys.stderr.write("Investigation MCP unavailable\n")
        return 1
    finally:
        if engine is not None:
            engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
