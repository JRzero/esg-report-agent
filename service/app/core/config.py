from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    app_env: str = 'development'
    app_debug: bool = False
    app_name: str = 'ESG Report Agent Service'
    database_url: str = 'postgresql+asyncpg://esg:esg@localhost:5432/esg'
    redis_url: str = 'redis://localhost:6379/0'
    storage_backend: str = 'local'
    local_storage_path: str = '.storage'
    minio_endpoint: str = 'localhost:9000'
    minio_access_key: str = 'minioadmin'
    minio_secret_key: str = 'minioadmin'
    minio_bucket: str = 'esg-report'
    minio_secure: bool = False
    jwt_secret: str = 'dev-secret-change-me'
    jwt_access_token_minutes: int = 30
    jwt_refresh_token_days: int = 14
    openviking_base_url: str = 'http://localhost:1933'
    openviking_api_key: str = ''
    llm_base_url: str = ''
    llm_api_key: str = ''
    llm_model: str = 'default'

@lru_cache
def get_settings() -> Settings:
    return Settings()
