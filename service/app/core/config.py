from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    app_debug: bool = False
    app_name: str = "ESG Report Agent Service"
    docs_enabled: bool = True
    security_hsts_enabled: bool = False

    database_url: str = "postgresql+asyncpg://esg:esg@localhost:5432/esg"
    redis_url: str = "redis://localhost:6379/0"

    storage_backend: str = "local"
    local_storage_path: str = ".storage"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "esg-report"
    minio_secure: bool = False

    jwt_secret: str = "dev-secret-change-me"
    jwt_access_token_minutes: int = Field(default=30, ge=1, le=1440)
    jwt_refresh_token_days: int = Field(default=14, ge=1, le=90)

    openviking_enabled: bool = False
    openviking_base_url: str = "http://localhost:1933"
    openviking_api_key: str = ""
    openviking_upload_mode: str = "local"
    openviking_reconcile_max_retries: int = Field(default=20, ge=1, le=1000)

    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = "default"
    llm_timeout_seconds: int = Field(default=120, ge=1, le=600)
    llm_max_retries: int = Field(default=2, ge=0, le=10)
    llm_retry_base_seconds: float = Field(default=0.25, ge=0, le=30)

    max_upload_bytes: int = Field(default=50 * 1024 * 1024, ge=1024)
    max_document_anchors: int = Field(default=20000, ge=100, le=1_000_000)
    max_document_text_chars: int = Field(default=10_000_000, ge=1000)
    task_stale_after_seconds: int = Field(default=15 * 60, ge=60, le=24 * 3600)
    document_stale_after_seconds: int = Field(default=15 * 60, ge=60, le=24 * 3600)

    @model_validator(mode="after")
    def validate_runtime_safety(self):
        env = self.app_env.lower()
        if env in {"production", "prod", "staging"}:
            if self.jwt_secret == "dev-secret-change-me" or len(self.jwt_secret) < 32:
                raise ValueError("JWT_SECRET must be at least 32 characters and non-default")
            if self.storage_backend == "minio" and (
                self.minio_access_key == "minioadmin" or self.minio_secret_key == "minioadmin"
            ):
                raise ValueError("Default MinIO credentials are forbidden outside development/test")
        if self.openviking_enabled and not self.openviking_base_url.startswith(("http://", "https://")):
            raise ValueError("OPENVIKING_BASE_URL must use http or https")
        if self.openviking_upload_mode not in {"local", "shared"}:
            raise ValueError("OPENVIKING_UPLOAD_MODE must be local or shared")
        if self.llm_base_url and not self.llm_base_url.startswith(("http://", "https://")):
            raise ValueError("LLM_BASE_URL must use http or https")
        if self.storage_backend not in {"local", "minio"}:
            raise ValueError("STORAGE_BACKEND must be local or minio")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
