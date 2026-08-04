from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from redis.asyncio import Redis
from redis.exceptions import ResponseError

from src.ingestion.queue import (
    INGESTION_CONSUMER_GROUP,
    INGESTION_STREAM_NAME,
    InvalidIngestionMessageError,
    RedisIngestionConsumer,
    RedisIngestionQueue,
)


def make_redis_client() -> tuple[Redis, AsyncMock]:
    redis_client = MagicMock(spec=Redis)
    xadd_mock = AsyncMock()

    redis_client.xadd = xadd_mock
    redis_client.hset = AsyncMock()
    xadd_mock.return_value = "123-0"

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


def make_consumer() -> tuple[
    RedisIngestionConsumer,
    AsyncMock,
    AsyncMock,
    AsyncMock,
    AsyncMock,
]:
    redis_client = MagicMock(spec=Redis)
    xgroup_create_mock = AsyncMock()
    xreadgroup_mock = AsyncMock()
    xautoclaim_mock = AsyncMock()
    xack_mock = AsyncMock()

    redis_client.xgroup_create = xgroup_create_mock
    redis_client.xreadgroup = xreadgroup_mock
    redis_client.xautoclaim = xautoclaim_mock
    redis_client.xack = xack_mock
    xautoclaim_mock.return_value = ["0-0", [], []]

    consumer = RedisIngestionConsumer(
        redis_client=redis_client,
        consumer_name="worker-1",
        block_milliseconds=250,
        claim_min_idle_milliseconds=1_000,
    )

    return (
        consumer,
        xgroup_create_mock,
        xreadgroup_mock,
        xautoclaim_mock,
        xack_mock,
    )


@pytest.mark.asyncio
async def test_ensure_group_creates_group_from_stream_start() -> None:
    consumer, xgroup_create_mock, _, _, _ = make_consumer()

    await consumer.ensure_group()

    xgroup_create_mock.assert_awaited_once_with(
        name=INGESTION_STREAM_NAME,
        groupname=INGESTION_CONSUMER_GROUP,
        id="0-0",
        mkstream=True,
    )


@pytest.mark.asyncio
async def test_ensure_group_accepts_existing_group() -> None:
    consumer, xgroup_create_mock, _, _, _ = make_consumer()
    xgroup_create_mock.side_effect = ResponseError(
        "BUSYGROUP Consumer Group name already exists",
    )

    await consumer.ensure_group()

    xgroup_create_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_ensure_group_propagates_unexpected_redis_error() -> None:
    consumer, xgroup_create_mock, _, _, _ = make_consumer()
    xgroup_create_mock.side_effect = ResponseError(
        "Redis command failed",
    )

    with pytest.raises(
        ResponseError,
        match="Redis command failed",
    ):
        await consumer.ensure_group()


@pytest.mark.asyncio
@pytest.mark.parametrize("use_bytes", [False, True])
async def test_read_returns_typed_ingestion_message(use_bytes: bool) -> None:
    consumer, _, xreadgroup_mock, xautoclaim_mock, _ = make_consumer()
    ingestion_job_id = uuid4()
    entry_id = "123-0"

    response: list[Any]

    if use_bytes:
        response = [
            (
                INGESTION_STREAM_NAME.encode(),
                [
                    (
                        entry_id.encode(),
                        {
                            b"ingestion_job_id": str(ingestion_job_id).encode(),
                        },
                    ),
                ],
            ),
        ]
    else:
        response = [
            (
                INGESTION_STREAM_NAME,
                [
                    (
                        entry_id,
                        {
                            "ingestion_job_id": str(ingestion_job_id),
                        },
                    ),
                ],
            ),
        ]

    xreadgroup_mock.return_value = response

    message = await consumer.read()

    assert message is not None
    assert message.entry_id == entry_id
    assert message.ingestion_job_id == ingestion_job_id
    xautoclaim_mock.assert_awaited_once_with(
        name=INGESTION_STREAM_NAME,
        groupname=INGESTION_CONSUMER_GROUP,
        consumername="worker-1",
        min_idle_time=1_000,
        start_id="0-0",
        count=1,
    )
    xreadgroup_mock.assert_awaited_once_with(
        groupname=INGESTION_CONSUMER_GROUP,
        consumername="worker-1",
        streams={
            INGESTION_STREAM_NAME: ">",
        },
        count=1,
        block=250,
    )


@pytest.mark.asyncio
async def test_read_returns_none_when_no_message_is_available() -> None:
    consumer, _, xreadgroup_mock, _, _ = make_consumer()
    xreadgroup_mock.return_value = []

    message = await consumer.read()

    assert message is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fields",
    [
        {},
        {
            "ingestion_job_id": "not-a-uuid",
        },
    ],
)
async def test_read_rejects_invalid_message(
    fields: dict[str, str],
) -> None:
    consumer, _, xreadgroup_mock, _, _ = make_consumer()
    xreadgroup_mock.return_value = [
        (
            INGESTION_STREAM_NAME,
            [
                (
                    "123-0",
                    fields,
                ),
            ],
        ),
    ]

    with pytest.raises(InvalidIngestionMessageError) as error_info:
        await consumer.read()

    assert error_info.value.entry_id == "123-0"


@pytest.mark.asyncio
async def test_acknowledge_acks_message_in_consumer_group() -> None:
    consumer, _, _, _, xack_mock = make_consumer()

    await consumer.acknowledge("123-0")

    xack_mock.assert_awaited_once_with(
        INGESTION_STREAM_NAME,
        INGESTION_CONSUMER_GROUP,
        "123-0",
    )


@pytest.mark.asyncio
async def test_read_returns_stale_claimed_message_before_new_message() -> None:
    consumer, _, xreadgroup_mock, xautoclaim_mock, _ = make_consumer()
    ingestion_job_id = uuid4()
    xautoclaim_mock.return_value = [
        "0-0",
        [
            (
                "old-0",
                {
                    "ingestion_job_id": str(ingestion_job_id),
                },
            ),
        ],
        [],
    ]

    message = await consumer.read()

    assert message is not None
    assert message.entry_id == "old-0"
    assert message.ingestion_job_id == ingestion_job_id
    xreadgroup_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_recover_requeues_running_job_without_pending_message() -> None:
    redis_client = MagicMock(spec=Redis)
    redis_client.hget = AsyncMock(return_value="old-0")
    redis_client.xpending_range = AsyncMock(return_value=[])
    redis_client.xadd = AsyncMock(return_value="new-0")
    redis_client.hset = AsyncMock()
    consumer = RedisIngestionConsumer(
        redis_client=redis_client,
        consumer_name="worker-1",
    )
    ingestion_job_id = uuid4()

    recovered = await consumer.recover([ingestion_job_id])

    assert recovered == 1
    redis_client.xpending_range.assert_awaited_once_with(
        name=INGESTION_STREAM_NAME,
        groupname=INGESTION_CONSUMER_GROUP,
        min="old-0",
        max="old-0",
        count=1,
    )
    redis_client.xadd.assert_awaited_once_with(
        INGESTION_STREAM_NAME,
        {"ingestion_job_id": str(ingestion_job_id)},
    )


@pytest.mark.asyncio
async def test_recover_keeps_existing_pending_message() -> None:
    redis_client = MagicMock(spec=Redis)
    redis_client.hget = AsyncMock(return_value="old-0")
    redis_client.xpending_range = AsyncMock(
        return_value=[
            {
                "message_id": "old-0",
                "consumer": "worker",
                "time_since_delivered": 100,
                "times_delivered": 1,
            }
        ]
    )
    redis_client.xadd = AsyncMock()
    consumer = RedisIngestionConsumer(
        redis_client=redis_client,
        consumer_name="worker-1",
    )

    recovered = await consumer.recover([uuid4()])

    assert recovered == 0
    redis_client.xadd.assert_not_awaited()
