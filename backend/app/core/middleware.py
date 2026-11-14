from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse


class BodyTooLarge(HTTPException):
    def __init__(self):
        super().__init__(413, "Request body exceeds upload limit")


class RequestSizeLimit:
    """Bound multipart spooling as well as the file read, including chunked requests."""

    def __init__(self, app, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        response = JSONResponse(
            {"error": {"code": "FILE_TOO_LARGE", "message": "Request body exceeds upload limit"}},
            status_code=413,
        )
        headers = dict(scope.get("headers", []))
        try:
            declared_size = int(headers.get(b"content-length", b"0"))
        except ValueError:
            declared_size = 0
        if declared_size > self.max_bytes:
            return await response(scope, receive, send)
        received = 0

        async def bounded_receive():
            nonlocal received
            message = await receive()
            received += len(message.get("body", b""))
            if received > self.max_bytes:
                raise BodyTooLarge()
            return message

        try:
            await self.app(scope, bounded_receive, send)
        except BodyTooLarge:
            await response(scope, receive, send)


class PublicReadOnly:
    """Deny mutations before body parsing, including unknown future endpoints."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["method"] not in ("GET", "HEAD", "OPTIONS"):
            response = JSONResponse(
                {
                    "error": {
                        "code": "PUBLIC_DEMO_READ_ONLY",
                        "message": "Synthetic public demonstration is read-only",
                    }
                },
                status_code=403,
            )
            return await response(scope, receive, send)
        return await self.app(scope, receive, send)
