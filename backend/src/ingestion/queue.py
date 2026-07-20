from typing import Protocol
from uuid import UUID

from redis.asyncio import Redis

INGESTION_STREAM_NAME = "trace:ingestion:jobs"


class IngestionQueue(Protocol):
    async def enqueue(
        self,
        *,
        ingestion_job_id: UUID,
    ) -> None: ...


class RedisIngestionQueue:
    def __init__(
        self,
        *,
        redis_client: Redis,
        stream_name: str = INGESTION_STREAM_NAME,
    ) -> None:
        self.redis_client = redis_client
        self.stream_name = stream_name

    async def enqueue(
        self,
        *,
        ingestion_job_id: UUID,
    ) -> None:
        await self.redis_client.xadd(
            self.stream_name,
            {
                "ingestion_job_id": str(ingestion_job_id),
            },
        )
