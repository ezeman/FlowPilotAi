from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    project_name: str = "ezeCraft AI API"
    api_prefix: str = "/api/v1"
    environment: str = Field(default="development", alias="ENVIRONMENT")
    secret_key: str = Field(default="change-me-secret", alias="SECRET_KEY")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 2
    database_url: str = Field(
        default="postgresql+psycopg2://postgres:postgres@postgres:5432/ezecraft_db",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://redis:6379/0", alias="REDIS_URL")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4.1-mini", alias="OPENAI_MODEL")
    openai_image_model: str = Field(default="gpt-image-1", alias="OPENAI_IMAGE_MODEL")
    facebook_graph_api_version: str = Field(default="v22.0", alias="FACEBOOK_GRAPH_API_VERSION")
    mock_external_services: bool = Field(default=True, alias="MOCK_EXTERNAL_SERVICES")
    encryption_key: str = Field(default="MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=", alias="ENCRYPTION_KEY")
    public_base_url: str = Field(default="http://localhost:3090", alias="PUBLIC_BASE_URL")
    generated_media_dir: str = Field(default="/app/generated_assets", alias="GENERATED_MEDIA_DIR")
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3090", "http://127.0.0.1:3090"], alias="CORS_ORIGINS")


@lru_cache
def get_settings() -> Settings:
    return Settings()
