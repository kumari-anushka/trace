from functools import lru_cache

from pydantic import field_validator, model_validator
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

    embedding_batch_size: int = 64
    embedding_provider: str = "local"

    openai_api_url: str = "https://api.openai.com/v1"
    openai_api_key: str | None = None
    openai_subsystem_enrichment_enabled: bool = False
    openai_subsystem_model: str = "gpt-5.6-sol"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_max_output_tokens: int = 800
    openai_max_retries: int = 2
    openai_max_retry_delay_seconds: float = 15.0
    openai_timeout_seconds: float = 60.0

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

    @field_validator("embedding_batch_size")
    @classmethod
    def validate_embedding_batch_size(cls, value: int) -> int:
        if value < 1 or value > 256:
            raise ValueError("embedding_batch_size must be between 1 and 256")
        return value

    @field_validator("embedding_provider")
    @classmethod
    def validate_embedding_provider(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"local", "openai"}:
            raise ValueError("embedding_provider must be local or openai")
        return normalized

    @field_validator("openai_subsystem_model", "openai_embedding_model")
    @classmethod
    def validate_openai_model(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("OpenAI model settings cannot be empty")
        return normalized

    @field_validator("openai_max_output_tokens")
    @classmethod
    def validate_openai_max_output_tokens(cls, value: int) -> int:
        if value < 1:
            raise ValueError("openai_max_output_tokens must be positive")
        return value

    @field_validator("openai_max_retries")
    @classmethod
    def validate_openai_max_retries(cls, value: int) -> int:
        if value < 0:
            raise ValueError("openai_max_retries cannot be negative")
        return value

    @field_validator("openai_max_retry_delay_seconds", "openai_timeout_seconds")
    @classmethod
    def validate_positive_openai_duration(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("OpenAI duration settings must be positive")
        return value

    @model_validator(mode="after")
    def validate_openai_enrichment_configuration(self) -> "Settings":
        if (self.openai_subsystem_enrichment_enabled or self.embedding_provider == "openai") and (
            not self.openai_api_key or not self.openai_api_key.strip()
        ):
            raise ValueError("openai_api_key is required when an OpenAI provider is enabled")
        return self

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
