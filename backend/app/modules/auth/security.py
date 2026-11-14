"""JWT verification and Argon2id hashing; token contents never leave cookies."""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from argon2.low_level import Type

from app.core.errors import AppError

ACCESS_AGE = timedelta(hours=24)
REFRESH_AGE = timedelta(days=7)
ISSUER = "invoice-exception-desk"
AUDIENCE = "invoice-desk-browser"
hasher = PasswordHasher(type=Type.ID)
DUMMY_HASH = hasher.hash(secrets.token_urlsafe(32))


def now():
    return datetime.now(UTC)


def password_matches(encoded: str, password: str) -> bool:
    try:
        return hasher.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue_token(settings, user_id: uuid.UUID, session_id: uuid.UUID, kind: str) -> str:
    issued = now()
    return jwt.encode(
        {
            "sub": str(user_id),
            "sid": str(session_id),
            "jti": str(uuid.uuid4()),
            "type": kind,
            "iat": issued,
            "exp": issued + (ACCESS_AGE if kind == "access" else REFRESH_AGE),
            "iss": ISSUER,
            "aud": AUDIENCE,
        },
        settings.auth_jwt_secret.get_secret_value(),
        algorithm="HS256",
    )


def decode_token(settings, token: str | None, kind: str) -> dict:
    if not token or len(token) > 4096:
        raise AppError(401, "UNAUTHORIZED", "Sign in to continue")
    try:
        claims = jwt.decode(
            token,
            settings.auth_jwt_secret.get_secret_value(),
            algorithms=["HS256"],
            issuer=ISSUER,
            audience=AUDIENCE,
            options={"require": ["sub", "sid", "jti", "type", "exp", "iat", "iss", "aud"]},
        )
        if claims["type"] != kind:
            raise ValueError("Wrong token purpose")
        for key in ("sub", "sid", "jti"):
            uuid.UUID(claims[key])
        return claims
    except jwt.ExpiredSignatureError as exc:
        raise AppError(
            401, "ACCESS_EXPIRED" if kind == "access" else "REFRESH_EXPIRED", "Sign in to continue"
        ) from exc
    except (jwt.InvalidTokenError, ValueError, TypeError, AttributeError) as exc:
        raise AppError(401, "UNAUTHORIZED", "Sign in to continue") from exc
