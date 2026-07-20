from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from redis.asyncio import Redis

from src.ingestion.queue import (
    INGESTION_STREAM_NAME,
    RedisIngestionQueue,
)


def make_redis_client() -> tuple[Redis, AsyncMock]:
    redis_client = MagicMock(spec=Redis)
    xadd_mock = AsyncMock()

    redis_client.xadd = xadd_mock

    return redis_client, xadd_mock


@pytest.mark.asyncio
async def test_enqueue_adds_ingestion_job_to_stream() -> None:
    redis_client, xadd_mock = make_redis_client()

    queue = RedisIngestionQueue(
        redis_client=redis_client,
    )

    ingestion_job_id = uuid4()

    await queue.enqueue(
        ingestion_job_id=ingestion_job_id,
    )

    xadd_mock.assert_awaited_once_with(
        INGESTION_STREAM_NAME,
        {
            "ingestion_job_id": str(ingestion_job_id),
        },
    )


@pytest.mark.asyncio
async def test_enqueue_propagates_redis_error() -> None:
    redis_client, xadd_mock = make_redis_client()

    xadd_mock.side_effect = RuntimeError(
        "Redis unavailable",
    )

    queue = RedisIngestionQueue(
        redis_client=redis_client,
    )

    ingestion_job_id = uuid4()

    with pytest.raises(
        RuntimeError,
        match="Redis unavailable",
    ):
        await queue.enqueue(
            ingestion_job_id=ingestion_job_id,
        )

    xadd_mock.assert_awaited_once_with(
        INGESTION_STREAM_NAME,
        {
            "ingestion_job_id": str(ingestion_job_id),
        },
    )
