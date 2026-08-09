import json
import math
from unittest.mock import AsyncMock

import httpx
import pytest

from src.ai.openai_embeddings import OpenAIEmbeddingProvider
from src.core.exceptions import OpenAIAPIError, RetryableOpenAIAPIError
from src.semantic.models import EMBEDDING_DIMENSIONS


def _payload(count: int) -> dict[str, object]:
    return {
        "object": "list",
        "data": [
            {
                "object": "embedding",
                "index": index,
                "embedding": [float(index + 1)] * EMBEDDING_DIMENSIONS,
            }
            for index in range(count)
        ],
    }


@pytest.mark.asyncio
async def test_openai_embedding_provider_requests_384_float_dimensions() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers["authorization"]
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=_payload(2))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        vectors = await OpenAIEmbeddingProvider(
            http_client=client,
            api_key="test-secret",
        ).embed(["architecture", "subsystem"])

    assert captured["authorization"] == "Bearer test-secret"
    assert captured["body"] == {
        "model": "text-embedding-3-small",
        "input": ["architecture", "subsystem"],
        "dimensions": EMBEDDING_DIMENSIONS,
        "encoding_format": "float",
    }
    assert len(vectors) == 2
    assert all(len(vector) == EMBEDDING_DIMENSIONS for vector in vectors)


@pytest.mark.asyncio
async def test_openai_embedding_provider_restores_provider_index_order() -> None:
    payload = _payload(2)
    data = payload["data"]
    assert isinstance(data, list)
    data.reverse()

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        vectors = await OpenAIEmbeddingProvider(
            http_client=client,
            api_key="test-secret",
        ).embed(["first", "second"])

    assert vectors[0][0] == 1.0
    assert vectors[1][0] == 2.0


@pytest.mark.asyncio
async def test_openai_embedding_provider_retries_transient_failures() -> None:
    attempts = 0
    sleep = AsyncMock()

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(503, headers={"retry-after": "0.2"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAIEmbeddingProvider(
            http_client=client,
            api_key="test-secret",
            max_retries=1,
            sleep=sleep,
        )
        with pytest.raises(RetryableOpenAIAPIError, match="status 503"):
            await provider.embed(["architecture"])

    assert attempts == 2
    sleep.assert_awaited_once_with(0.2)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"data": []},
        {"data": [{"index": 0, "embedding": [1.0]}]},
        {"data": [{"index": 1, "embedding": [1.0] * EMBEDDING_DIMENSIONS}]},
        {
            "data": [
                {
                    "index": 0,
                    "embedding": [math.inf] + [1.0] * (EMBEDDING_DIMENSIONS - 1),
                }
            ]
        },
        {
            "data": [
                {
                    "index": 0,
                    "embedding": [True] + [1.0] * (EMBEDDING_DIMENSIONS - 1),
                }
            ]
        },
    ],
)
async def test_openai_embedding_provider_rejects_invalid_vectors(
    payload: dict[str, object],
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=json.dumps(payload).encode(),
            headers={"content-type": "application/json"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(OpenAIAPIError):
            await OpenAIEmbeddingProvider(
                http_client=client,
                api_key="test-secret",
            ).embed(["architecture"])
