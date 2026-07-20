from typing import Annotated

from fastapi import Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.dependencies import get_session
from src.ingestion.queue import RedisIngestionQueue
from src.ingestion.service import IngestionService
from src.ingestion.store import IngestionJobStore

SessionDependency = Annotated[
    AsyncSession,
    Depends(get_session),
]


def get_ingestion_service(
    session: SessionDependency,
) -> IngestionService:
    store = IngestionJobStore(
        session=session,
    )

    return IngestionService(
        store=store,
    )


def get_ingestion_queue(
    request: Request,
) -> RedisIngestionQueue:
    redis_client: Redis = request.app.state.redis_client

    return RedisIngestionQueue(
        redis_client=redis_client,
    )
