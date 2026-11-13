from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    database_url: str = "postgresql+psycopg://app:app@localhost:5433/invoices"
    ai_mode: Literal["mock", "gemini"] = "mock"
    gemini_api_key: SecretStr = SecretStr("")
    gemini_model: str = ""
    gemini_timeout_seconds: int = Field(default=10, ge=1, le=15)
    gemini_max_attempts: int = Field(default=3, ge=1, le=3)
    money_tolerance: Decimal = Field(default=Decimal("0.01"), ge=0, le=Decimal("0.01"))
    demo_basic_user: str = "demo"
    demo_basic_password: SecretStr = SecretStr("")
    n8n_integration_key: SecretStr = SecretStr("")
    storage_dir: Path = Path("storage/uploads")
    fixtures_dir: Path = Path(__file__).resolve().parents[3] / "fixtures"
    max_upload_bytes: int = Field(default=8 * 1024 * 1024, ge=1, le=8 * 1024 * 1024)
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    @model_validator(mode="after")
    def require_credentials(self):
        password = self.demo_basic_password.get_secret_value()
        if not self.demo_basic_user.strip() or not password or password == "CHANGE_ME":
            raise ValueError("Set DEMO_BASIC_USER and DEMO_BASIC_PASSWORD before startup")
        if "*" in self.cors_origins:
            raise ValueError("CORS_ORIGINS must list explicit frontend origins")
        return self
