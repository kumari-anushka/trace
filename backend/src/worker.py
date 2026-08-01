import asyncio
import logging
import os
import socket

from redis.asyncio import Redis

from src.core.config import get_settings
from src.db import models as _models  # noqa: F401
from src.db.session import async_session_factory, engine
from src.ingestion.processor import FoundationIngestionProcessor
from src.ingestion.queue import RedisIngestionConsumer
from src.ingestion.runner import IngestionWorker
from src.ingestion.service import IngestionService, IngestionStageService
from src.ingestion.store import IngestionJobStore, IngestionStageStore
from src.repository_versions.service import RepositoryVersionService
from src.repository_versions.store import RepositoryVersionStore


async def run_worker() -> None:
    settings = get_settings()
    redis_client = Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=5.0,
        socket_timeout=10.0,
        health_check_interval=30,
    )
    consumer_name = f"{socket.gethostname()}-{os.getpid()}"

    try:
        async with async_session_factory() as session:
            ingestion_service = IngestionService(
                store=IngestionJobStore(session=session),
            )
            stage_service = IngestionStageService(
                store=IngestionStageStore(session=session),
            )
            repository_version_service = RepositoryVersionService(
                store=RepositoryVersionStore(session=session),
            )
            processor = FoundationIngestionProcessor(
                session=session,
                ingestion_service=ingestion_service,
                stage_service=stage_service,
                repository_version_service=repository_version_service,
            )
            worker = IngestionWorker(
                session=session,
                consumer=RedisIngestionConsumer(
                    redis_client=redis_client,
                    consumer_name=consumer_name,
                ),
                ingestion_service=ingestion_service,
                processor=processor,
            )

            await worker.run_forever()
    finally:
        await redis_client.aclose()
        await engine.dispose()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
