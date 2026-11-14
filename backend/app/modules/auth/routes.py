import secrets
import uuid
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy import case, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import AuthLoginWindow, AuthSession, AuthUser
from app.db.session import get_session
from app.modules.auth.cookies import (
    clear_cookies,
    csrf_valid,
    names,
    new_csrf,
    require_csrf,
    set_cookie,
    set_tokens,
)
from app.modules.auth.security import (
    DUMMY_HASH,
    REFRESH_AGE,
    decode_token,
    digest,
    hasher,
    issue_token,
    now,
    password_matches,
)
from app.modules.auth.service import Principal, active_session, current_principal

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])
Db = Annotated[Session, Depends(get_session)]


class LoginInput(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    username: str = Field(min_length=1, max_length=200)
    password: SecretStr = Field(min_length=1, max_length=1024)


def user_view(user, sid):
    return {
        "id": str(user.id),
        "username": user.username,
        "role": user.role,
        "session_id": str(sid),
    }


def limited_login(db, request):
    # Persistent per-IP window, shared by workers. Store only a keyed IP digest.
    settings = request.app.state.settings
    import hashlib
    import hmac

    key = hmac.new(
        settings.auth_jwt_secret.get_secret_value().encode(),
        f"login:{request.client.host if request.client else 'unknown'}".encode(),
        hashlib.sha256,
    ).hexdigest()
    stamp = now()
    expired = AuthLoginWindow.started_at < stamp - timedelta(minutes=5)
    statement = insert(AuthLoginWindow).values(key_hash=key, started_at=stamp, attempts=1)
    statement = statement.on_conflict_do_update(
        index_elements=[AuthLoginWindow.key_hash],
        set_={
            "started_at": case((expired, stamp), else_=AuthLoginWindow.started_at),
            "attempts": case((expired, 1), else_=AuthLoginWindow.attempts + 1),
        },
    ).returning(AuthLoginWindow.attempts)
    attempts = db.scalar(statement)
    db.commit()
    if attempts > 20:
        raise AppError(
            429, "LOGIN_RATE_LIMITED", "Too many sign-in attempts. Try again in five minutes"
        )


@router.get("/csrf")
def csrf(request: Request, response: Response, db: Db):
    settings = request.app.state.settings
    sid = "anonymous"
    for index, kind in ((1, "refresh"), (0, "access")):
        try:
            claims = decode_token(settings, request.cookies.get(names(settings)[index]), kind)
            row, _ = active_session(db, claims)
            sid = str(row.id)
            break
        except AppError:
            continue
    token = request.cookies.get(names(settings)[2], "")
    if not csrf_valid(settings, token, sid):
        token = new_csrf(settings, sid)
    set_cookie(response, settings, names(settings)[2], token, int(REFRESH_AGE.total_seconds()))
    return {"csrf_token": token}


@router.post("/login")
def login(body: LoginInput, request: Request, response: Response, db: Db):
    require_csrf(request)
    settings = request.app.state.settings
    limited_login(db, request)
    user = db.scalar(select(AuthUser).where(AuthUser.username == body.username))
    matched = password_matches(
        user.password_hash if user else DUMMY_HASH, body.password.get_secret_value()
    )
    if not matched or not user or not user.is_active or user.role != "OPERATOR":
        raise AppError(401, "INVALID_CREDENTIALS", "Username or password is incorrect")
    if hasher.check_needs_rehash(user.password_hash):
        user.password_hash = hasher.hash(body.password.get_secret_value())
    sid = uuid.uuid4()
    access = issue_token(settings, user.id, sid, "access")
    refresh = issue_token(settings, user.id, sid, "refresh")
    row = AuthSession(
        id=sid, user_id=user.id, refresh_hash=digest(refresh), expires_at=now() + REFRESH_AGE
    )
    db.add(row)
    db.commit()
    token = new_csrf(settings, str(sid))
    set_tokens(response, settings, access, refresh, token)
    return {"user": user_view(user, sid), "csrf_token": token}


@router.get("/me")
def me(response: Response, principal: Annotated[Principal, Depends(current_principal)]):
    response.headers["Cache-Control"] = "no-store"
    return user_view(principal, principal.session_id)


@router.post("/refresh")
def refresh(request: Request, response: Response, db: Db):
    settings = request.app.state.settings
    raw = request.cookies.get(names(settings)[1])
    claims = decode_token(settings, raw, "refresh")
    require_csrf(request, claims["sid"])
    row, user = active_session(db, claims, lock=True)
    if not secrets.compare_digest(row.refresh_hash, digest(raw)):
        row.revoked_at, row.revoke_reason = now(), "refresh_reuse"
        db.commit()  # Revocation must survive the error response.
        failure = JSONResponse(
            {"error": {"code": "REFRESH_REUSED", "message": "Session revoked. Sign in again"}},
            status_code=401,
        )
        clear_cookies(failure, settings)
        return failure
    access = issue_token(settings, user.id, row.id, "access")
    rotated = issue_token(settings, user.id, row.id, "refresh")
    row.refresh_hash, row.expires_at = digest(rotated), now() + REFRESH_AGE
    db.commit()
    token = request.cookies[names(settings)[2]]
    set_tokens(response, settings, access, rotated, token)
    return {"user": user_view(user, row.id), "csrf_token": token}


@router.post("/logout", status_code=204)
def logout(request: Request, db: Db):
    settings = request.app.state.settings
    claims = None
    for index, kind in ((1, "refresh"), (0, "access")):
        try:
            claims = decode_token(settings, request.cookies.get(names(settings)[index]), kind)
            break
        except AppError:
            continue
    require_csrf(request, claims["sid"] if claims else None)
    if claims:
        row = db.scalar(
            select(AuthSession).where(AuthSession.id == uuid.UUID(claims["sid"])).with_for_update()
        )
        if row and str(row.user_id) == claims["sub"] and not row.revoked_at:
            row.revoked_at, row.revoke_reason = now(), "logout"
            db.commit()
    response = Response(status_code=204)
    clear_cookies(response, settings)
    return response
