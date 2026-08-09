from typing import Any

import pytest
from pydantic import ValidationError

from src.core.config import Settings


def _settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "database_url": "postgresql+psycopg://trace:trace@localhost:5432/trace",
        "redis_url": "redis://localhost:6379/0",
        **overrides,
    }
    return Settings(_env_file=None, **values)


def test_openai_enrichment_is_disabled_without_credentials_by_default() -> None:
    settings = _settings()

    assert settings.openai_subsystem_enrichment_enabled is False
    assert settings.openai_api_key is None


def test_openai_enrichment_requires_an_api_key_when_enabled() -> None:
    with pytest.raises(ValidationError, match="openai_api_key is required"):
        _settings(openai_subsystem_enrichment_enabled=True)


def test_openai_enrichment_accepts_explicit_credentials() -> None:
    settings = _settings(
        openai_subsystem_enrichment_enabled=True,
        openai_api_key="test-secret",
    )

    assert settings.openai_subsystem_enrichment_enabled is True
    assert settings.openai_api_key == "test-secret"


def test_openai_embedding_provider_requires_an_api_key() -> None:
    with pytest.raises(ValidationError, match="openai_api_key is required"):
        _settings(embedding_provider="openai")


def test_openai_provider_rejects_a_blank_api_key() -> None:
    with pytest.raises(ValidationError, match="openai_api_key is required"):
        _settings(embedding_provider="openai", openai_api_key="   ")


def test_openai_provider_rejects_a_blank_model() -> None:
    with pytest.raises(ValidationError, match="OpenAI model settings cannot be empty"):
        _settings(openai_embedding_model="   ")


def test_embedding_provider_rejects_unknown_values() -> None:
    with pytest.raises(ValidationError, match="embedding_provider must be local or openai"):
        _settings(embedding_provider="unknown")
