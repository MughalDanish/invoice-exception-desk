from decimal import Decimal
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    database_url: str = "postgresql+psycopg://app:app@localhost:5433/invoices"
    public_demo: bool = False
    ai_mode: Literal["mock", "gemini"] = "mock"
    investigation_mode: Literal["mock"] = "mock"
    gemini_api_key: SecretStr = SecretStr("")
    gemini_model: str = ""
    gemini_timeout_seconds: int = Field(default=60, ge=1, le=60)
    gemini_max_attempts: int = Field(default=3, ge=1, le=3)
    money_tolerance: Decimal = Field(default=Decimal("0.01"), ge=0, le=Decimal("0.01"))
    auth_jwt_secret: SecretStr = SecretStr("")
    auth_bootstrap_username: str = "demo"
    auth_bootstrap_password: SecretStr = SecretStr("")
    auth_cookie_secure: bool = True
    auth_cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    n8n_integration_key: SecretStr = SecretStr("")
    storage_dir: Path = Path("storage/uploads")
    fixtures_dir: Path = Path(__file__).resolve().parents[3] / "fixtures"
    max_upload_bytes: int = Field(default=8 * 1024 * 1024, ge=1, le=8 * 1024 * 1024)
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    @model_validator(mode="after")
    def require_credentials(self):
        if self.public_demo:
            if self.ai_mode != "mock":
                raise ValueError("Public demonstration requires mock mode")
            return self
        if (
            len(self.auth_jwt_secret.get_secret_value().encode()) < 32
            or self.auth_jwt_secret.get_secret_value() == "CHANGE_ME"
        ):
            raise ValueError("Set AUTH_JWT_SECRET to a random secret of at least 32 bytes")
        if "*" in self.cors_origins:
            raise ValueError("CORS_ORIGINS must list explicit frontend origins")
        if self.auth_cookie_samesite == "none" and not self.auth_cookie_secure:
            raise ValueError("SameSite=None requires Secure cookies")
        for origin in self.cors_origins:
            parsed = urlsplit(origin)
            if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.path:
                raise ValueError("CORS_ORIGINS must contain exact HTTP(S) origins")
            if not self.auth_cookie_secure and parsed.hostname not in (
                "localhost",
                "127.0.0.1",
                "::1",
                "testserver",
            ):
                raise ValueError("Non-Secure auth cookies are permitted only for local development")
        return self
