from dataclasses import dataclass
from typing import Any, Protocol, cast
from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import ResponseError

INGESTION_STREAM_NAME = "trace:ingestion:jobs"
INGESTION_CONSUMER_GROUP = "trace:ingestion:workers"

RedisValue = str | bytes
RedisStreamResponse = list[
    tuple[
        RedisValue,
        list[tuple[RedisValue, dict[RedisValue, RedisValue]]],
    ]
]


@dataclass(frozen=True, slots=True)
class IngestionMessage:
    entry_id: str
    ingestion_job_id: UUID


class InvalidIngestionMessageError(ValueError):
    def __init__(
        self,
        *,
        entry_id: str,
        message: str,
    ) -> None:
        self.entry_id = entry_id
        super().__init__(message)


class IngestionQueue(Protocol):
    async def enqueue(
        self,
        *,
        ingestion_job_id: UUID,
    ) -> None: ...


class IngestionConsumer(Protocol):
    async def ensure_group(self) -> None: ...

    async def read(self) -> IngestionMessage | None: ...

    async def acknowledge(self, entry_id: str) -> None: ...


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


class RedisIngestionConsumer:
    def __init__(
        self,
        *,
        redis_client: Redis,
        consumer_name: str,
        stream_name: str = INGESTION_STREAM_NAME,
        group_name: str = INGESTION_CONSUMER_GROUP,
        block_milliseconds: int = 5_000,
        claim_min_idle_milliseconds: int = 60_000,
    ) -> None:
        self.redis_client = redis_client
        self.consumer_name = consumer_name
        self.stream_name = stream_name
        self.group_name = group_name
        self.block_milliseconds = block_milliseconds
        self.claim_min_idle_milliseconds = claim_min_idle_milliseconds

    async def ensure_group(self) -> None:
        try:
            await self.redis_client.xgroup_create(
                name=self.stream_name,
                groupname=self.group_name,
                id="0-0",
                mkstream=True,
            )
        except ResponseError as error:
            if "BUSYGROUP" not in str(error):
                raise

    async def read(self) -> IngestionMessage | None:
        claimed_message = await self._read_claimed_message()

        if claimed_message is not None:
            return claimed_message

        response = await self.redis_client.xreadgroup(
            groupname=self.group_name,
            consumername=self.consumer_name,
            streams={
                self.stream_name: ">",
            },
            count=1,
            block=self.block_milliseconds,
        )

        streams = cast(RedisStreamResponse, response)

        if not streams or not streams[0][1]:
            return None

        entry_id_value, fields = streams[0][1][0]
        return self._parse_message(
            entry_id_value=entry_id_value,
            fields=fields,
        )

    async def _read_claimed_message(self) -> IngestionMessage | None:
        response = await self.redis_client.xautoclaim(
            name=self.stream_name,
            groupname=self.group_name,
            consumername=self.consumer_name,
            min_idle_time=self.claim_min_idle_milliseconds,
            start_id="0-0",
            count=1,
        )
        claim_response: list[Any] = response

        if len(claim_response) < 2:
            return None

        entries = cast(
            list[tuple[RedisValue, dict[RedisValue, RedisValue]]],
            claim_response[1],
        )

        if not entries:
            return None

        entry_id_value, fields = entries[0]
        return self._parse_message(
            entry_id_value=entry_id_value,
            fields=fields,
        )

    def _parse_message(
        self,
        *,
        entry_id_value: RedisValue,
        fields: dict[RedisValue, RedisValue],
    ) -> IngestionMessage:
        entry_id = self._decode(entry_id_value)
        ingestion_job_id_value = fields.get("ingestion_job_id") or fields.get(
            b"ingestion_job_id",
        )

        if ingestion_job_id_value is None:
            raise InvalidIngestionMessageError(
                entry_id=entry_id,
                message="Ingestion message is missing ingestion_job_id",
            )

        try:
            ingestion_job_id = UUID(
                self._decode(ingestion_job_id_value),
            )
        except ValueError as error:
            raise InvalidIngestionMessageError(
                entry_id=entry_id,
                message="Ingestion message contains an invalid ingestion_job_id",
            ) from error

        return IngestionMessage(
            entry_id=entry_id,
            ingestion_job_id=ingestion_job_id,
        )

    async def acknowledge(self, entry_id: str) -> None:
        await self.redis_client.xack(
            self.stream_name,
            self.group_name,
            entry_id,
        )

    @staticmethod
    def _decode(value: RedisValue) -> str:
        if isinstance(value, bytes):
            return value.decode("utf-8")

        return value
