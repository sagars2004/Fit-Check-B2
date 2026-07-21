from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProviderMode(StrEnum):
    MOCK = "mock"
    LIVE = "live"


class StorageMode(StrEnum):
    LOCAL = "local"
    B2 = "b2"


class Settings(BaseSettings):
    """Server-only configuration.

    Model IDs intentionally default to empty values. A live image workflow is
    blocked until the configured GMI account capability probe has selected an
    explicit model ID.
    """

    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "test", "staging", "production"] = "development"
    provider_mode: ProviderMode = ProviderMode.MOCK
    storage_mode: StorageMode = StorageMode.LOCAL
    web_origin: str = "http://localhost:3000"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"

    database_url: str = "sqlite+aiosqlite:///./.data/fit_check.db"
    auto_create_schema: bool = True
    local_media_root: Path = Path("./local-media")
    public_media_base_url: str = "http://localhost:8000/v1/media"
    fit_check_storage_prefix: str = "fit-check"
    demo_user_id: str = "00000000-0000-0000-0000-000000000001"

    b2_endpoint_url: str | None = None
    b2_region: str | None = None
    b2_bucket: str | None = None
    b2_key_id: SecretStr | None = None
    b2_app_key: SecretStr | None = None
    b2_prefix: str = "fit-check"
    b2_presign_expires_seconds: int = Field(default=900, ge=60, le=3600)

    gmi_api_key: SecretStr | None = None
    gmi_org_id: str | None = None
    gmi_request_queue_base_url: str = "https://console.gmicloud.ai/api/v1/ie/requestqueue"
    gmi_llm_base_url: str = "https://api.gmi-serving.com/v1"
    gmi_vision_model: str | None = None
    gmi_image_model: str | None = None
    gmi_tryon_model: str | None = None
    gmi_fallback_image_model: str | None = None
    gmi_generation_timeout_seconds: int = Field(default=180, ge=30, le=900)
    gmi_max_retries: int = Field(default=2, ge=0, le=5)
    enable_provider_smoke_tests: bool = False

    nvidia_api_key: SecretStr | None = None
    nvidia_fallback_image_model: str | None = None
    weather_provider: Literal["open-meteo"] = "open-meteo"
    daily_generation_quota: int = Field(default=3, ge=1, le=100)
    max_concurrent_generations: int = Field(default=2, ge=1, le=10)
    sentry_dsn: str | None = None

    @field_validator("fit_check_storage_prefix", "b2_prefix")
    @classmethod
    def validate_prefix(cls, value: str) -> str:
        normalized = value.strip("/")
        if not normalized or ".." in normalized:
            raise ValueError("storage prefixes must be non-empty and may not contain '..'")
        return normalized

    @model_validator(mode="after")
    def validate_live_mode(self) -> Settings:
        if self.provider_mode is ProviderMode.LIVE:
            missing = []
            if self.gmi_api_key is None:
                missing.append("GMI_API_KEY")
            if self.storage_mode is not StorageMode.B2:
                missing.append("STORAGE_MODE=b2")
            if not self.b2_bucket:
                missing.append("B2_BUCKET")
            if self.b2_key_id is None:
                missing.append("B2_KEY_ID")
            if self.b2_app_key is None:
                missing.append("B2_APP_KEY")
            if missing:
                raise ValueError(
                    "live provider mode requires " + ", ".join(missing) + "; use mock mode locally"
                )
        return self

    @property
    def is_mock(self) -> bool:
        return self.provider_mode is ProviderMode.MOCK

    @property
    def media_root(self) -> Path:
        return self.local_media_root.expanduser().resolve()

    def has_gmi_credentials(self) -> bool:
        return self.gmi_api_key is not None and bool(self.gmi_api_key.get_secret_value())

    def selected_image_model(self) -> str:
        if not self.gmi_image_model:
            raise RuntimeError(
                "No GMI image model is configured. Run the capability smoke test, then set "
                "GMI_IMAGE_MODEL server-side."
            )
        return self.gmi_image_model


@lru_cache
def get_settings() -> Settings:
    return Settings()

