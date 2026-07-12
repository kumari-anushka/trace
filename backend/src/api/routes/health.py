from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db_session

router = APIRouter(prefix="/health", tags=["health"])

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
