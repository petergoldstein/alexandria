from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://postgres:localdev@localhost:5432/alexandria"

    # Security
    encryption_key: str = "CHANGE_ME_IN_PRODUCTION"  # For API key encryption

    # Storage backend selection: "local", "s3", or "r2"
    storage_backend: str = "local"

    # Local storage
    local_storage_path: str = "./storage"

    # AWS S3
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_bucket_name: str = ""
    s3_endpoint_url: str = ""
    s3_region: str = "us-east-1"

    # Cloudflare R2 (S3-compatible)
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = "alexandria-files"
    r2_endpoint: str = ""
    r2_public_url_base: str = ""  # For public bucket access

    # App settings
    debug: bool = True
    cors_origins: list[str] = ["http://localhost:3000"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Ignore extra env vars like TEST_DATABASE_URL in CI


@lru_cache
def get_settings() -> Settings:
    return Settings()
