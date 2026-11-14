"""Host-only cookies and signed, session-bound double-submit CSRF protection."""

import hashlib
import hmac
import secrets
from urllib.parse import urlsplit

from fastapi import Request, Response

from app.core.errors import AppError
from app.modules.auth.security import ACCESS_AGE, REFRESH_AGE


def names(settings):
    if settings.auth_cookie_secure:
        return "__Host-ied_access", "__Secure-ied_refresh", "__Host-ied_csrf"
    return "ied_access", "ied_refresh", "ied_csrf"


def set_cookie(response: Response, settings, name: str, value: str, age: int, path="/"):
    response.set_cookie(
        name,
        value,
        max_age=age,
        path=path,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"


def new_csrf(settings, sid: str = "anonymous") -> str:
    body = f"{sid}.{secrets.token_urlsafe(32)}"
    signature = hmac.new(
        settings.auth_jwt_secret.get_secret_value().encode(),
        f"csrf:{body}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{body}.{signature}"


def csrf_valid(settings, token: str, sid: str | None = None) -> bool:
    if len(token) > 256:
        return False
    try:
        subject, nonce, signature = token.split(".")
    except ValueError:
        return False
    expected = hmac.new(
        settings.auth_jwt_secret.get_secret_value().encode(),
        f"csrf:{subject}.{nonce}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return (
        bool(nonce) and (sid is None or subject == sid) and hmac.compare_digest(signature, expected)
    )


def require_csrf(request: Request, sid: str | None = None):
    settings = request.app.state.settings
    origin = request.headers.get("origin")
    referer = request.headers.get("referer")
    if not origin and referer:
        parsed = urlsplit(referer)
        origin = f"{parsed.scheme}://{parsed.netloc}"
    allowed = {*settings.cors_origins, str(request.base_url).rstrip("/")}
    if origin and origin not in allowed:
        raise AppError(403, "CSRF_REJECTED", "Request origin is not allowed")
    cookie = request.cookies.get(names(settings)[2], "")
    header = request.headers.get("x-csrf-token", "")
    if (
        not cookie
        or not header
        or not hmac.compare_digest(cookie, header)
        or not csrf_valid(settings, cookie, sid)
    ):
        raise AppError(403, "CSRF_REJECTED", "Refresh the page before submitting this action")


def set_tokens(response: Response, settings, access: str, refresh: str, csrf: str):
    access_name, refresh_name, csrf_name = names(settings)
    set_cookie(response, settings, access_name, access, int(ACCESS_AGE.total_seconds()))
    set_cookie(
        response, settings, refresh_name, refresh, int(REFRESH_AGE.total_seconds()), "/api/v1/auth"
    )
    set_cookie(response, settings, csrf_name, csrf, int(REFRESH_AGE.total_seconds()))


def clear_cookies(response: Response, settings):
    access, refresh, csrf = names(settings)
    for name, path in ((access, "/"), (refresh, "/api/v1/auth"), (csrf, "/")):
        response.delete_cookie(
            name,
            path=path,
            httponly=True,
            secure=settings.auth_cookie_secure,
            samesite=settings.auth_cookie_samesite,
        )
    response.headers["Cache-Control"] = "no-store"
