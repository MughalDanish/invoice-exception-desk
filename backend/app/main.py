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
from app.core.middleware import PublicReadOnly, RequestSizeLimit
from app.db.session import build_engine, build_session_factory
from app.modules.auth.routes import router as auth_router
from app.modules.investigation.routes import router as investigation_router
from app.modules.invoices.integration import router as integration_router
from app.modules.invoices.routes import Db, router
from app.modules.public_demo import create_public_router, load_public_data


def create_app(settings: Settings | None = None, engine=None) -> FastAPI:
    settings = settings or Settings()
    engine = None if settings.public_demo else (engine or build_engine(settings.database_url))

    @asynccontextmanager
    async def lifespan(app):
        yield
        if engine is not None:
            engine.dispose()

    app = FastAPI(
        title="Invoice Exception Desk",
        version="0.5.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = build_session_factory(engine) if engine is not None else None
    app.add_middleware(RequestSizeLimit, max_bytes=settings.max_upload_bytes + 64 * 1024)
    if settings.public_demo:
        app.add_middleware(PublicReadOnly)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Content-Type", "X-CSRF-Token", "X-Integration-Key", "Idempotency-Key"],
    )

    @app.exception_handler(AppError)
    async def app_error(request: Request, exc: AppError):
        return JSONResponse(
            {"error": {"code": exc.code, "message": exc.message}},
            status_code=exc.status,
            headers={"Cache-Control": "no-store"},
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

    @app.get("/api/v1/config")
    def configuration():
        return {
            "public_demo": settings.public_demo,
            "read_only": settings.public_demo,
            "synthetic": settings.public_demo,
            "ai_mode": settings.ai_mode,
        }

    if settings.public_demo:
        data = load_public_data()
        app.include_router(create_public_router(data))

        @app.get("/health")
        def public_health():
            return {
                "status": "ok",
                "mode": "public_demo",
                "database": "not_used",
                "ai_mode": "mock",
            }

        return app

    @app.get("/health")
    def health(session: Db):
        revision = session.scalar(text("SELECT version_num FROM alembic_version"))
        if revision != "0007_investigation_documents":
            raise AppError(
                503, "MIGRATIONS_REQUIRED", "Apply database migrations before using this backend"
            )
        return {"status": "ok", "database": "ready", "ai_mode": settings.ai_mode}

    @app.get("/openapi.json", dependencies=[Depends(require_operator)], include_in_schema=False)
    def openapi():
        return app.openapi()

    @app.get("/docs", dependencies=[Depends(require_operator)], include_in_schema=False)
    def docs():
        return get_swagger_ui_html(openapi_url="/openapi.json", title=app.title)

    app.include_router(auth_router)
    app.include_router(router)
    app.include_router(integration_router)
    app.include_router(investigation_router)
    return app
