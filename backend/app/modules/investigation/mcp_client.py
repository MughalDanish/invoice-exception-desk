"""Synchronous host facade over the pinned official asynchronous MCP client.

One owning task creates, uses and closes SDK cancel scopes on the same thread.
The model receives definitions/results only, never delegation or process settings.
"""

import asyncio
import concurrent.futures
import json
import logging
import os
import queue
import sys
import threading
import traceback
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import get_args

from app.db.models import InvestigationRun
from app.modules.investigation.delegation import assert_run_authorized, issue_capability
from app.modules.investigation.mcp_adapter import MAX_RESULT_BYTES, TOOL_DESCRIPTIONS
from app.modules.investigation.schemas import ToolName, ToolResult


class MCPUnavailable(RuntimeError):
    """Sanitized failure; never includes subprocess output or protocol payloads."""


def subprocess_environment(settings, capability):
    # SDK itself inherits only a fixed runtime allowlist. Explicitly override its
    # runtime keys; no application secrets are inherited and dotenv is disabled.
    env = {
        key: os.environ[key]
        for key in ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "COMSPEC")
        if key in os.environ
    }
    env.update(
        {
            "PYTHONPATH": str(Path(__file__).resolve().parents[3]),
            "PYTHONDONTWRITEBYTECODE": "1",
            "DATABASE_URL": settings.database_url,
            "AUTH_JWT_SECRET": settings.auth_jwt_secret.get_secret_value(),
            "IED_MCP_CAPABILITY": capability,
            "PUBLIC_DEMO": "false",
            "AI_MODE": "mock",
            "INVESTIGATION_MODE": "mock",
        }
    )
    return env


class MCPClient:
    def __init__(self, settings, session_factory, claim, timeout=10, startup_timeout=None):
        self.settings, self.factory, self.claim = settings, session_factory, claim
        self.timeout = min(10.0, max(0.1, float(timeout)))
        self.startup_timeout = min(
            30.0,
            max(
                0.1,
                float(
                    startup_timeout
                    if startup_timeout is not None
                    else getattr(settings, "investigation_mcp_startup_seconds", 20)
                ),
            ),
        )
        self.definitions = []
        self._requests = queue.Queue()
        self._ready = concurrent.futures.Future()
        self._thread = None
        self._closed = False

    def __enter__(self):
        self._capability = issue_capability(self.settings, self.factory, self.claim)
        with self.factory() as session:
            deadline = (session.get(InvestigationRun, self.claim.run_id).budget_metadata or {}).get(
                "deadline"
            )
        if deadline:
            remaining = max(
                0.001, (datetime.fromisoformat(deadline) - datetime.now(UTC)).total_seconds()
            )
            self.startup_timeout = min(self.startup_timeout, remaining)
            self.timeout = min(self.timeout, remaining)
        self._thread = threading.Thread(target=self._run, name="investigation-mcp", daemon=True)
        self._thread.start()
        try:
            self.definitions = self._ready.result(timeout=self.startup_timeout + 2)
        except Exception as exc:
            self.close()
            raise MCPUnavailable("MCP startup unavailable") from exc
        return self

    def _run(self):
        try:
            asyncio.run(self._session())
        except Exception as exc:  # noqa: BLE001
            leaf = exc
            while isinstance(leaf, BaseExceptionGroup) and leaf.exceptions:
                leaf = leaf.exceptions[0]
            frames = traceback.extract_tb(leaf.__traceback__)
            site = f"{frames[-1].name}:{frames[-1].lineno}" if frames else "unknown"
            logging.getLogger(__name__).warning(
                "Investigation MCP failed error_type=%s error_site=%s", type(leaf).__name__, site
            )
            if not self._ready.done():
                self._ready.set_exception(MCPUnavailable("MCP startup unavailable"))
        finally:
            self._capability = None
            while not self._requests.empty():
                item = self._requests.get_nowait()
                if item and not item[2].done():
                    item[2].set_exception(MCPUnavailable("MCP connection closed"))

    async def _session(self):
        async with asyncio.timeout(self.startup_timeout) as startup:
            await self._connected_session(startup)

    async def _connected_session(self, startup):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "app.modules.investigation.mcp_stdio"],
            env=subprocess_environment(self.settings, self._capability),
        )
        with open(os.devnull, "w", encoding="utf-8") as stderr:
            async with stdio_client(params, errlog=stderr) as (read, write):
                async with ClientSession(
                    read, write, read_timeout_seconds=timedelta(seconds=self.startup_timeout)
                ) as client:
                    await client.initialize()
                    listed = await client.list_tools()
                    definitions = self._validate_definitions(listed)
                    startup.reschedule(None)
                    self._ready.set_result(definitions)
                    while True:
                        item = await asyncio.to_thread(self._requests.get)
                        if item is None:
                            return
                        name, arguments, future = item
                        try:
                            result = await asyncio.wait_for(
                                client.call_tool(
                                    name,
                                    arguments,
                                    read_timeout_seconds=timedelta(seconds=self.timeout),
                                ),
                                self.timeout,
                            )
                            if (
                                result.isError
                                or len(result.model_dump_json().encode()) > MAX_RESULT_BYTES
                            ):
                                raise MCPUnavailable("MCP tool result unavailable")
                            data = result.structuredContent
                            if not isinstance(data, dict):
                                raise MCPUnavailable("MCP structured result missing")
                            value = ToolResult.model_validate_json(json.dumps(data))
                            if value.name != name:
                                raise MCPUnavailable("MCP result scope mismatch")
                            if not future.done():
                                future.set_result(value)
                        except Exception as exc:
                            if not future.done():
                                future.set_exception(MCPUnavailable("MCP tool call unavailable"))
                            # Transport/auth errors terminate rather than silently fall back.
                            raise MCPUnavailable("MCP tool call unavailable") from exc

    @staticmethod
    def _validate_definitions(listed):
        if (
            listed.nextCursor
            or len(listed.tools) != len(get_args(ToolName))
            or {tool.name for tool in listed.tools} != set(get_args(ToolName))
        ):
            raise MCPUnavailable("MCP tool allowlist mismatch")
        definitions = []
        for tool in listed.tools:
            if (
                tool.inputSchema
                != {"type": "object", "properties": {}, "additionalProperties": False}
                or tool.description != TOOL_DESCRIPTIONS[tool.name]
                or not tool.annotations
                or tool.annotations.readOnlyHint is not True
                or tool.annotations.destructiveHint is not False
            ):
                raise MCPUnavailable("MCP tool schema mismatch")
            definitions.append(
                {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.inputSchema,
                }
            )
        return definitions

    def call(self, name, arguments=None):
        if (
            self._closed
            or not self._thread
            or not self._thread.is_alive()
            or name not in get_args(ToolName)
            or (arguments is not None and arguments != {})
        ):
            raise MCPUnavailable("Invalid MCP tool request")
        assert_run_authorized(self.settings, self.factory, self.claim)
        future = concurrent.futures.Future()
        self._requests.put((name, {}, future))
        try:
            result = future.result(timeout=self.timeout + 1)
            assert_run_authorized(self.settings, self.factory, self.claim)
            return result
        except Exception as exc:
            self.close()
            raise MCPUnavailable("MCP tool call unavailable") from exc

    def close(self):
        if not self._closed:
            self._closed = True
            self._requests.put(None)
        if self._thread:
            self._thread.join(timeout=max(self.timeout, self.startup_timeout) + 5)
        self._capability = None

    def __exit__(self, *_):
        self.close()
