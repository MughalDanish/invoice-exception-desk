"""Short-lived MCP-only delegation. Browser tokens are never forwarded or persisted."""

import json
import uuid
from datetime import UTC, datetime, timedelta

import jwt

from app.core.errors import AppError
from app.db.models import InvestigationRun, Invoice
from app.modules.approvals.service import payload_hash
from app.modules.auth.service import active_session
from app.modules.investigation.queue import Claim, database_now, owned
from app.modules.investigation.schemas import InvoiceSnapshot

AUDIENCE = "invoice-desk-investigation-mcp"
ISSUER = "invoice-desk-worker"


def assert_run_authorized(settings, factory, claim):
    """Fresh DB authorization before model/tool/publication; returns frozen evidence."""
    from app.modules.investigation.service import matches

    if settings.public_demo:
        raise AppError(403, "MCP_UNAUTHORIZED", "Private operator scope required")
    with factory() as session:
        run = session.get(InvestigationRun, claim.run_id)
        if (
            not owned(run, claim, database_now(session))
            or not run.requested_user_id
            or not run.requested_session_id
        ):
            raise AppError(403, "MCP_UNAUTHORIZED", "Investigation authorization unavailable")
        active_session(
            session, {"sub": str(run.requested_user_id), "sid": str(run.requested_session_id)}
        )
        deadline = (run.budget_metadata or {}).get("deadline")
        if deadline and datetime.fromisoformat(deadline) <= datetime.now(UTC):
            raise AppError(409, "INVESTIGATION_DEADLINE", "Investigation deadline reached")
        invoice = session.get(Invoice, run.invoice_id)
        if not matches(invoice, run, session):
            raise AppError(409, "INVESTIGATION_STALE", "Investigation evidence changed")
        return InvoiceSnapshot.model_validate_json(json.dumps(run.snapshot))


def issue_capability(settings, factory, claim):
    snapshot = assert_run_authorized(settings, factory, claim)
    with factory() as session:
        run = session.get(InvestigationRun, claim.run_id)
        auth, _ = active_session(
            session, {"sub": str(run.requested_user_id), "sid": str(run.requested_session_id)}
        )
        issued = datetime.now(UTC)
        expiry = min(issued + timedelta(minutes=5), auth.expires_at)
        deadline = (run.budget_metadata or {}).get("deadline")
        if deadline:
            expiry = min(expiry, datetime.fromisoformat(deadline))
        return jwt.encode(
            {
                "iss": ISSUER,
                "aud": AUDIENCE,
                "type": "investigation_mcp",
                "iat": issued,
                "exp": expiry,
                "sub": str(run.requested_user_id),
                "sid": str(run.requested_session_id),
                "rid": str(run.id),
                "iid": str(run.invoice_id),
                "digest": payload_hash(snapshot.model_dump(mode="json")),
                "fence": claim.fence,
                "owner": claim.owner,
            },
            settings.auth_jwt_secret.get_secret_value(),
            algorithm="HS256",
        )


class RunToolHost:
    """Fixed run scope loaded from signed host authority, never model arguments."""

    def __init__(self, settings, factory, capability):
        self.settings, self.factory = settings, factory
        try:
            self.claims = jwt.decode(
                capability,
                settings.auth_jwt_secret.get_secret_value(),
                algorithms=["HS256"],
                issuer=ISSUER,
                audience=AUDIENCE,
                options={
                    "require": [
                        "iss",
                        "aud",
                        "type",
                        "iat",
                        "exp",
                        "sub",
                        "sid",
                        "rid",
                        "iid",
                        "digest",
                        "fence",
                        "owner",
                    ]
                },
            )
            if self.claims["type"] != "investigation_mcp" or type(self.claims["fence"]) is not int:
                raise ValueError("Invalid delegation")
            self.claim = Claim(
                uuid.UUID(self.claims["rid"]), self.claims["owner"], self.claims["fence"]
            )
        except (jwt.InvalidTokenError, ValueError, TypeError, KeyError) as exc:
            raise AppError(401, "MCP_UNAUTHORIZED", "Invalid investigation delegation") from exc
        self.authorize()

    def authorize(self):
        if datetime.now(UTC).timestamp() >= self.claims["exp"]:
            raise AppError(401, "MCP_UNAUTHORIZED", "Investigation delegation expired")
        snapshot = assert_run_authorized(self.settings, self.factory, self.claim)
        with self.factory() as session:
            run = session.get(InvestigationRun, self.claim.run_id)
            if (
                str(run.requested_user_id) != self.claims["sub"]
                or str(run.requested_session_id) != self.claims["sid"]
                or str(snapshot.invoice_id) != self.claims["iid"]
                or payload_hash(snapshot.model_dump(mode="json")) != self.claims["digest"]
            ):
                raise AppError(403, "MCP_UNAUTHORIZED", "Investigation delegation scope changed")
        return snapshot

    def call(self, name):
        from app.modules.investigation.schemas import ToolRequest
        from app.modules.investigation.tools import ReadOnlyTools

        snapshot = self.authorize()
        return (
            ReadOnlyTools(snapshot)
            .call(
                ToolRequest(
                    name=name,
                    invoice_id=snapshot.invoice_id,
                    supplier_key=snapshot.lookup.supplier_key if snapshot.lookup else "",
                )
            )
            .model_dump(mode="json")
        )
