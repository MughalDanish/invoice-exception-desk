import secrets
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import APIKeyHeader

from app.core.errors import AppError

integration_header = APIKeyHeader(name="X-Integration-Key", auto_error=False)


def require_integration(
    request: Request, key: Annotated[str | None, Depends(integration_header)]
) -> str:
    expected = request.app.state.settings.n8n_integration_key.get_secret_value()
    if (
        not expected
        or expected == "CHANGE_ME"
        or not key
        or not secrets.compare_digest(key.encode(), expected.encode())
    ):
        raise AppError(403, "INTEGRATION_UNAUTHORIZED", "Valid integration credentials required")
    return "integration:n8n"


def require_operator(request: Request) -> str:
    from app.modules.auth.service import current_principal
    return current_principal(request).username
