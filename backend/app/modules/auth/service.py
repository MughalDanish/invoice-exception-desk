"""Session authorization uses a separate transaction from financial operations."""

import uuid
from dataclasses import dataclass

from fastapi import Request
from sqlalchemy import select

from app.core.errors import AppError
from app.db.models import AuthSession, AuthUser
from app.modules.auth.cookies import names, require_csrf
from app.modules.auth.security import decode_token, now


@dataclass(frozen=True)
class Principal:
    id: uuid.UUID
    username: str
    role: str
    session_id: uuid.UUID


def active_session(db, claims, lock=False):
    query = select(AuthSession).where(AuthSession.id == uuid.UUID(claims["sid"]))
    if lock:
        query = query.with_for_update()
    row = db.scalar(query)
    if not row or row.revoked_at or row.expires_at <= now() or str(row.user_id) != claims["sub"]:
        raise AppError(401, "SESSION_REVOKED", "Sign in to continue")
    user = db.get(AuthUser, row.user_id)
    if not user or not user.is_active or user.role != "OPERATOR":
        raise AppError(401, "SESSION_REVOKED", "Sign in to continue")
    return row, user


def current_principal(request: Request) -> Principal:
    settings = request.app.state.settings
    raw = request.cookies.get(names(settings)[0])
    if not raw and (
        request.url.path != "/api/v1/auth/me" or request.cookies.get(names(settings)[1])
    ):
        raise AppError(401, "ACCESS_REQUIRED", "Authentication needs renewal")
    claims = decode_token(settings, raw, "access")
    with request.app.state.session_factory() as db:
        row, user = active_session(db, claims)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            require_csrf(request, str(row.id))
        return Principal(user.id, user.username, user.role, row.id)
