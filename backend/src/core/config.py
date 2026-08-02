from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Trace API"
    environment: str = "development"

    database_url: str
    redis_url: str

    github_api_url: str = "https://api.github.com"
    github_token: str | None = None
    github_max_retries: int = 3
    github_max_retry_delay_seconds: float = 30.0
    github_issue_limit: int = 200
    github_pull_request_limit: int = 100
    github_review_limit_per_pull_request: int = 100
    github_changed_file_limit_per_artifact: int = 300
    github_commit_limit: int = 100
    github_release_limit: int = 100
    github_contributor_limit: int = 100
    github_label_limit: int = 200
    github_archive_max_bytes: int = 250_000_000
    github_source_file_max_bytes: int = 1_000_000

    cors_origins: str = "http://localhost:5173"

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: object) -> object:
        if not isinstance(value, str):
            return value

        if value.startswith("postgresql://"):
            return value.replace(
                "postgresql://",
                "postgresql+psycopg://",
                1,
            )

        if value.startswith("postgres://"):
            return value.replace(
                "postgres://",
                "postgresql+psycopg://",
                1,
            )

        return value

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
