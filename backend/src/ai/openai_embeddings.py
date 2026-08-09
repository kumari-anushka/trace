from __future__ import annotations

import asyncio
import math
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

import httpx

from src.core.exceptions import OpenAIAPIError, RetryableOpenAIAPIError
from src.semantic.embeddings import EmbeddingProviderInfo
from src.semantic.models import EMBEDDING_DIMENSIONS

DEFAULT_OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_OPENAI_API_URL = "https://api.openai.com/v1"
RETRYABLE_STATUS_CODES = frozenset({408, 409, 429, 500, 502, 503, 504})
Sleep = Callable[[float], Awaitable[None]]


class OpenAIEmbeddingProvider:
    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient,
        api_key: str,
        model: str = DEFAULT_OPENAI_EMBEDDING_MODEL,
        api_url: str = DEFAULT_OPENAI_API_URL,
        max_retries: int = 2,
        max_retry_delay_seconds: float = 15.0,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        if not api_key.strip():
            raise ValueError("OpenAI API key cannot be empty")
        if not model.strip():
            raise ValueError("OpenAI embedding model cannot be empty")
        if max_retries < 0:
            raise ValueError("OpenAI max_retries cannot be negative")
        if max_retry_delay_seconds < 0:
            raise ValueError("OpenAI max_retry_delay_seconds cannot be negative")
        self.http_client = http_client
        self.api_key = api_key
        self.model = model.strip()
        self.api_url = api_url.rstrip("/")
        self.max_retries = max_retries
        self.max_retry_delay_seconds = max_retry_delay_seconds
        self.sleep = sleep

    @property
    def info(self) -> EmbeddingProviderInfo:
        return EmbeddingProviderInfo(
            provider="openai",
            model=self.model,
            model_revision=None,
            dimensions=EMBEDDING_DIMENSIONS,
        )

    async def embed(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        if not texts:
            return ()
        payload = await self._request(
            {
                "model": self.model,
                "input": list(texts),
                "dimensions": EMBEDDING_DIMENSIONS,
                "encoding_format": "float",
            }
        )
        return _parse_embeddings(payload, expected_count=len(texts))

    async def _request(self, body: dict[str, object]) -> dict[str, Any]:
        for attempt in range(self.max_retries + 1):
            try:
                response = await self.http_client.post(
                    f"{self.api_url}/embeddings",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
            except (httpx.TimeoutException, httpx.NetworkError) as error:
                if attempt >= self.max_retries:
                    raise RetryableOpenAIAPIError(
                        "OpenAI embeddings request failed after retries"
                    ) from error
                await self.sleep(self._retry_delay(attempt, None))
                continue

            if response.status_code in RETRYABLE_STATUS_CODES:
                if attempt >= self.max_retries:
                    raise RetryableOpenAIAPIError(
                        "OpenAI embeddings request failed with status "
                        f"{response.status_code} after retries"
                    )
                await self.sleep(self._retry_delay(attempt, response.headers.get("retry-after")))
                continue
            if response.is_error:
                raise OpenAIAPIError(
                    f"OpenAI embeddings request failed with status {response.status_code}"
                )
            try:
                payload = response.json()
            except ValueError as error:
                raise OpenAIAPIError("OpenAI embeddings API returned invalid JSON") from error
            if not isinstance(payload, dict):
                raise OpenAIAPIError("OpenAI embeddings API returned an unexpected response")
            return payload
        raise AssertionError("OpenAI embeddings retry loop exhausted unexpectedly")

    def _retry_delay(self, attempt: int, retry_after: str | None) -> float:
        if retry_after is not None:
            try:
                return min(self.max_retry_delay_seconds, max(0.0, float(retry_after)))
            except ValueError:
                pass
        return min(self.max_retry_delay_seconds, float(2**attempt))


def _parse_embeddings(
    payload: dict[str, Any], *, expected_count: int
) -> tuple[tuple[float, ...], ...]:
    data = payload.get("data")
    if not isinstance(data, list) or len(data) != expected_count:
        raise OpenAIAPIError("OpenAI embeddings API returned the wrong vector count")
    indexed: dict[int, tuple[float, ...]] = {}
    for item in data:
        if not isinstance(item, dict):
            raise OpenAIAPIError("OpenAI embeddings API returned an invalid data item")
        index = item.get("index")
        embedding = item.get("embedding")
        if not isinstance(index, int) or not isinstance(embedding, list):
            raise OpenAIAPIError("OpenAI embeddings API returned an invalid vector")
        if index in indexed or index < 0 or index >= expected_count:
            raise OpenAIAPIError("OpenAI embeddings API returned an invalid vector index")
        if len(embedding) != EMBEDDING_DIMENSIONS or any(
            isinstance(value, bool)
            or not isinstance(value, int | float)
            or not math.isfinite(float(value))
            for value in embedding
        ):
            raise OpenAIAPIError(
                f"OpenAI embeddings API must return {EMBEDDING_DIMENSIONS} numeric dimensions"
            )
        indexed[index] = tuple(float(value) for value in embedding)
    if set(indexed) != set(range(expected_count)):
        raise OpenAIAPIError("OpenAI embeddings API returned incomplete vector indexes")
    return tuple(indexed[index] for index in range(expected_count))
