from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.ingestion.models import (
    IngestionStage,
    IngestionStageStatus,
)
from src.ingestion.store import IngestionStageStore


def make_ingestion_stage(
    *,
    ingestion_job_id: UUID | None = None,
    name: str = "prepare",
    position: int = 0,
) -> IngestionStage:
    now = datetime.now(UTC)

    ingestion_stage = IngestionStage(
        ingestion_job_id=ingestion_job_id or uuid4(),
        name=name,
        position=position,
        status=IngestionStageStatus.PENDING,
        progress=0,
    )

    ingestion_stage.id = uuid4()
    ingestion_stage.created_at = now
    ingestion_stage.updated_at = now
    ingestion_stage.started_at = None
    ingestion_stage.completed_at = None
    ingestion_stage.error_message = None

    return ingestion_stage


def make_store() -> tuple[IngestionStageStore, AsyncMock]:
    session = AsyncMock(spec=AsyncSession)

    return IngestionStageStore(session=session), session


@pytest.mark.asyncio
async def test_create_adds_pending_stage_and_flushes() -> None:
    store, session = make_store()
    ingestion_job_id = uuid4()

    ingestion_stage = await store.create(
        ingestion_job_id=ingestion_job_id,
        name="prepare",
        position=0,
    )

    assert ingestion_stage.ingestion_job_id == ingestion_job_id
    assert ingestion_stage.name == "prepare"
    assert ingestion_stage.position == 0
    assert ingestion_stage.status is IngestionStageStatus.PENDING
    assert ingestion_stage.progress == 0
    session.add.assert_called_once_with(ingestion_stage)
    session.flush.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_get_by_id_returns_stage() -> None:
    store, session = make_store()
    ingestion_stage = make_ingestion_stage()
    session.get.return_value = ingestion_stage

    returned_stage = await store.get_by_id(
        ingestion_stage.id,
    )

    assert returned_stage is ingestion_stage
    session.get.assert_awaited_once_with(
        IngestionStage,
        ingestion_stage.id,
    )


@pytest.mark.asyncio
async def test_list_by_ingestion_job_returns_stages_in_store_order() -> None:
    store, session = make_store()
    ingestion_job_id = uuid4()
    stages = [
        make_ingestion_stage(
            ingestion_job_id=ingestion_job_id,
            name="prepare",
            position=0,
        ),
        make_ingestion_stage(
            ingestion_job_id=ingestion_job_id,
            name="finalize",
            position=1,
        ),
    ]

    scalar_result = MagicMock()
    scalar_result.all.return_value = stages
    result = MagicMock()
    result.scalars.return_value = scalar_result
    session.execute.return_value = result

    returned_stages = await store.list_by_ingestion_job(
        ingestion_job_id,
    )

    assert returned_stages == stages
    session.execute.assert_awaited_once()
    result.scalars.assert_called_once_with()
    scalar_result.all.assert_called_once_with()


@pytest.mark.asyncio
async def test_flush_flushes_and_returns_stage() -> None:
    store, session = make_store()
    ingestion_stage = make_ingestion_stage()

    returned_stage = await store.flush(ingestion_stage)

    assert returned_stage is ingestion_stage
    session.flush.assert_awaited_once_with()
