"""Local MCP stdio adapter. Authorization and invoice scope belong to the host.

No public listener, autonomous authority, filesystem or network tool is exposed.
Protocol subset: initialize, initialized, ping, tools/list and tools/call.
"""

import json
import uuid
from typing import get_args

from app.core.errors import AppError
from app.db.models import Invoice
from app.modules.auth.security import decode_token
from app.modules.auth.service import active_session
from app.modules.investigation.schemas import ToolName, ToolRequest
from app.modules.investigation.tools import ReadOnlyTools

PROTOCOL_VERSION = "2025-11-25"
MAX_FRAME_BYTES = 16_384
MAX_RESULT_BYTES = 65_536


class OperatorToolHost:
    """Trusted launch-time scope; caller arguments can never select another invoice."""

    def __init__(self, settings, session_factory, access_token: str, invoice_id: uuid.UUID):
        if settings.public_demo or not isinstance(invoice_id, uuid.UUID):
            raise ValueError("Private operator scope required")
        self.settings = settings
        self.session_factory = session_factory
        self._access_token = access_token
        self.invoice_id = invoice_id

    def authorize(self):
        claims = decode_token(self.settings, self._access_token, "access")
        with self.session_factory() as session:
            active_session(session, claims)

    def call(self, name):
        # Import at call time: use the same current bounded capture as the HTTP API.
        from app.modules.investigation.service import snapshot_invoice

        claims = decode_token(self.settings, self._access_token, "access")
        with self.session_factory() as session:
            active_session(session, claims)
            invoice = session.get(Invoice, self.invoice_id)
            if invoice is None:
                raise AppError(404, "INVOICE_NOT_FOUND", "Invoice not found")
            snapshot = snapshot_invoice(session, invoice)
        return (
            ReadOnlyTools(snapshot)
            .call(
                ToolRequest(
                    name=name,
                    invoice_id=self.invoice_id,
                    supplier_key=snapshot.lookup.supplier_key if snapshot.lookup else "",
                )
            )
            .model_dump(mode="json")
        )


def _error(request_id, code, message):
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


class LocalMCPServer:
    """Small, explicit protocol surface; unsupported capabilities are not advertised."""

    def __init__(self, host: OperatorToolHost):
        self.host = host
        self.initialized = False
        self.ready = False

    def handle(self, message):
        if not isinstance(message, dict):
            return _error(None, -32600, "Invalid request")
        request_id = message.get("id")
        notification = "id" not in message
        if (
            message.get("jsonrpc") != "2.0"
            or not isinstance(message.get("method"), str)
            or set(message) - {"jsonrpc", "id", "method", "params"}
            or (not notification and (type(request_id) not in (int, str)))
        ):
            return _error(None, -32600, "Invalid request")
        method = message["method"]
        params = message.get("params", {})
        if notification:
            if method == "notifications/initialized" and self.initialized and params == {}:
                self.ready = True
            return None
        if not isinstance(params, dict):
            return _error(request_id, -32602, "Invalid parameters")
        try:
            self.host.authorize()
            if method == "initialize":
                if self.initialized:
                    return _error(request_id, -32600, "Already initialized")
                if (
                    set(params) - {"protocolVersion", "capabilities", "clientInfo", "_meta"}
                    or not isinstance(params.get("protocolVersion"), str)
                    or not isinstance(params.get("capabilities"), dict)
                    or not isinstance(params.get("clientInfo"), dict)
                    or not all(
                        isinstance(params["clientInfo"].get(key), str)
                        for key in ("name", "version")
                    )
                ):
                    return _error(request_id, -32602, "Invalid initialization")
                # Spec negotiation: return our supported version; client must disconnect
                # if it cannot support it. Never pretend to support an arbitrary version.
                self.initialized = True
                result = {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "invoice-desk-read-only", "version": "1.0.0"},
                }
            elif method == "ping":
                if params:
                    return _error(request_id, -32602, "Invalid parameters")
                result = {}
            elif not self.ready:
                return _error(request_id, -32600, "Initialization required")
            elif method == "tools/list":
                if params:
                    return _error(request_id, -32602, "Invalid parameters")
                result = {
                    "tools": [
                        {
                            "name": name,
                            "description": "Read bounded evidence for the host-authorized invoice.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {},
                                "additionalProperties": False,
                            },
                            "annotations": {
                                "readOnlyHint": True,
                                "destructiveHint": False,
                                "idempotentHint": True,
                                "openWorldHint": False,
                            },
                        }
                        for name in get_args(ToolName)
                    ]
                }
            elif method == "tools/call":
                if (
                    set(params) - {"name", "arguments", "_meta"}
                    or params.get("name") not in get_args(ToolName)
                    or params.get("arguments", {}) != {}
                ):
                    return _error(request_id, -32602, "Invalid tool parameters")
                data = self.host.call(params["name"])
                result = {
                    "content": [{"type": "text", "text": json.dumps(data, separators=(",", ":"))}],
                    "structuredContent": data,
                    "isError": False,
                }
            else:
                return _error(request_id, -32601, "Method not found")
            response = {"jsonrpc": "2.0", "id": request_id, "result": result}
            if len(json.dumps(response).encode("utf-8")) > MAX_RESULT_BYTES:
                return _error(request_id, -32603, "Result exceeds safe limit")
            return response
        except AppError:
            return _error(request_id, -32001, "Authorization or invoice access unavailable")
        except Exception:
            # Never send exception strings, auth material, SQL or source payloads.
            return _error(request_id, -32603, "Read-only tool unavailable")


def serve(server: LocalMCPServer, reader, writer):
    """UTF-8 newline frames. Overlong frames close the transport, never accumulate."""
    while True:
        frame = reader.readline(MAX_FRAME_BYTES + 1)
        if not frame:
            return
        if len(frame) > MAX_FRAME_BYTES:
            response = _error(None, -32600, "Frame exceeds safe limit")
            writer.write(json.dumps(response).encode("utf-8") + b"\n")
            writer.flush()
            return
        try:
            message = json.loads(frame.decode("utf-8"))
        except (ValueError, UnicodeDecodeError, RecursionError):
            response = _error(None, -32700, "Parse error")
        else:
            response = server.handle(message)
        if response is not None:
            writer.write(json.dumps(response, separators=(",", ":")).encode("utf-8") + b"\n")
            writer.flush()
