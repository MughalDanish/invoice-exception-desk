from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException
from starlette.middleware.cors import CORSMiddleware

from app.core.auth import require_operator
from app.core.config import Settings
from app.core.errors import AppError
from app.core.middleware import RequestSizeLimit
from app.db.session import build_engine, build_session_factory
from app.modules.invoices.routes import Db, router


def create_app(settings: Settings | None = None, engine=None) -> FastAPI:
    settings = settings or Settings()
    engine = engine or build_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(app):
        yield
        engine.dispose()

    app = FastAPI(
        title="Invoice Exception Desk",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = build_session_factory(engine)
    app.add_middleware(RequestSizeLimit, max_bytes=settings.max_upload_bytes + 64 * 1024)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.exception_handler(AppError)
    async def app_error(request: Request, exc: AppError):
        return JSONResponse(
            {"error": {"code": exc.code, "message": exc.message}},
            status_code=exc.status,
            headers={"WWW-Authenticate": "Basic"} if exc.status == 401 else None,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        # Do not echo arbitrary invalid inputs (which may include credentials).
        return JSONResponse(
            {"error": {"code": "INVALID_REQUEST", "message": "Invalid request parameters"}},
            status_code=422,
        )

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return JSONResponse(
            {
                "error": {
                    "code": "FILE_TOO_LARGE" if exc.status_code == 413 else "HTTP_ERROR",
                    "message": str(exc.detail),
                }
            },
            status_code=exc.status_code,
            headers=exc.headers,
        )

    @app.exception_handler(SQLAlchemyError)
    async def db_error(request: Request, exc: SQLAlchemyError):
        return JSONResponse(
            {"error": {"code": "DATABASE_UNAVAILABLE", "message": "Database operation failed"}},
            status_code=503,
        )

    @app.get("/health")
    def health(session: Db):
        session.execute(text("SELECT 1 FROM alembic_version LIMIT 1"))
        return {"status": "ok", "database": "ready", "ai_mode": settings.ai_mode}

    @app.get("/openapi.json", dependencies=[Depends(require_operator)], include_in_schema=False)
    def openapi():
        return app.openapi()

    @app.get("/docs", dependencies=[Depends(require_operator)], include_in_schema=False)
    def docs():
        return get_swagger_ui_html(openapi_url="/openapi.json", title=app.title)

    app.include_router(router)
    return app
