from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.cache.redis import redis_client
from src.db.session import get_db_session

router = APIRouter(prefix="/health", tags=["Health"])

DatabaseSession = Annotated[
    AsyncSession,
    Depends(get_db_session),
]


@router.get("")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/database")
async def database_health_check(
    session: DatabaseSession,
) -> dict[str, str]:
    await session.execute(text("SELECT 1"))

    return {
        "status": "ok",
        "database": "connected",
    }


@router.get("/redis")
async def redis_health_check() -> dict[str, str]:
    await redis_client.ping()

    return {
        "status": "ok",
        "redis": "connected",
    }


@router.get("/ready")
async def readiness_check(session: DatabaseSession) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    await redis_client.ping()

    return {
        "status": "ok",
        "database": "connected",
        "redis": "connected",
    }
