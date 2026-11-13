import secrets
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.core.errors import AppError

basic = HTTPBasic(auto_error=False)


def require_operator(
    request: Request,
    credentials: Annotated[HTTPBasicCredentials | None, Depends(basic)],
) -> str:
    settings = request.app.state.settings
    if credentials is None:
        raise AppError(401, "UNAUTHORIZED", "Operator authentication required")
    user_ok = secrets.compare_digest(
        credentials.username.encode("utf-8"), settings.demo_basic_user.encode("utf-8")
    )
    password_ok = secrets.compare_digest(
        credentials.password.encode("utf-8"),
        settings.demo_basic_password.get_secret_value().encode("utf-8"),
    )
    if not (user_ok and password_ok):
        raise AppError(401, "UNAUTHORIZED", "Invalid operator credentials")
    return credentials.username
