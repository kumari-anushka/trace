from collections.abc import Callable
from uuid import UUID, uuid4

import httpx
import pytest
from redis.asyncio import Redis

from src.core.config import get_settings
from src.db.session import async_session_factory
from src.github.client import GitHubClient
from src.github.dependencies import get_github_client
from src.ingestion.dependencies import get_ingestion_queue
from src.ingestion.processor import (
    FOUNDATION_STAGE_NAME,
    FoundationIngestionProcessor,
)
from src.ingestion.queue import RedisIngestionConsumer, RedisIngestionQueue
from src.ingestion.runner import IngestionWorker
from src.ingestion.service import IngestionService, IngestionStageService
from src.ingestion.store import IngestionJobStore, IngestionStageStore
from src.main import create_app
from src.repositories.store import RepositoryStore
from src.repository_versions.service import RepositoryVersionService
from src.repository_versions.store import RepositoryVersionStore


def make_github_handler(
    *,
    owner: str,
    name: str,
    github_id: int,
    github_url: str,
    commit_sha: str,
) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == f"/repos/{owner}/{name}":
            return httpx.Response(
                200,
                json={
                    "id": github_id,
                    "name": name,
                    "full_name": f"{owner}/{name}",
                    "html_url": github_url,
                    "default_branch": "main",
                    "private": False,
                    "archived": False,
                    "disabled": False,
                    "owner": {
                        "login": owner,
                    },
                },
            )

        if request.url.path == f"/repos/{owner}/{name}/commits/main":
            return httpx.Response(
                200,
                json={
                    "sha": commit_sha,
                },
            )

        return httpx.Response(404)

    return handler


@pytest.mark.integration
@pytest.mark.asyncio
async def test_submission_queue_worker_and_progress_survive_fresh_requests() -> None:
    """Prove the Week 1 flow across API, PostgreSQL, Redis, and worker layers."""
    settings = get_settings()
    test_id = uuid4().hex
    owner = f"trace-e2e-{test_id[:8]}"
    name = f"repository-{test_id[8:16]}"
    github_url = f"https://github.com/{owner}/{name}"
    github_id = uuid4().int % (2**63 - 1)
    commit_sha = f"{test_id}{test_id[:8]}"
    stream_name = f"trace:test:ingestion:{test_id}"
    group_name = f"trace:test:workers:{test_id}"

    redis_client = Redis.from_url(
        settings.redis_url,
        decode_responses=True,
    )
    queue = RedisIngestionQueue(
        redis_client=redis_client,
        stream_name=stream_name,
    )
    consumer = RedisIngestionConsumer(
        redis_client=redis_client,
        consumer_name=f"test-worker-{test_id}",
        stream_name=stream_name,
        group_name=group_name,
        block_milliseconds=100,
    )
    github_http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            make_github_handler(
                owner=owner,
                name=name,
                github_id=github_id,
                github_url=github_url,
                commit_sha=commit_sha,
            ),
        ),
    )
    github_client = GitHubClient(
        http_client=github_http_client,
        api_url="https://api.github.test",
        token=None,
    )
    app = create_app()

    def override_github_client() -> GitHubClient:
        return github_client

    def override_ingestion_queue() -> RedisIngestionQueue:
        return queue

    app.dependency_overrides[get_github_client] = override_github_client
    app.dependency_overrides[get_ingestion_queue] = override_ingestion_queue

    repository_id: UUID | None = None

    try:
        await consumer.ensure_group()

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as api_client:
            submission_response = await api_client.post(
                "/api/repositories",
                json={
                    "github_url": github_url,
                },
            )

            assert submission_response.status_code == 201
            submission = submission_response.json()
            repository_id = UUID(submission["repository"]["id"])
            ingestion_job_id = UUID(submission["ingestion_job"]["id"])
            assert submission["ingestion_job"]["status"] == "queued"
            assert submission["ingestion_job"]["progress"] == 0

            queued_response = await api_client.get(
                f"/api/repositories/{repository_id}/ingestion",
            )

            assert queued_response.status_code == 200
            assert queued_response.json()["ingestion_job"]["status"] == "queued"
            assert queued_response.json()["stages"] == []

        async with async_session_factory() as worker_session:
            ingestion_service = IngestionService(
                store=IngestionJobStore(session=worker_session),
            )
            stage_service = IngestionStageService(
                store=IngestionStageStore(session=worker_session),
            )
            processor = FoundationIngestionProcessor(
                session=worker_session,
                ingestion_service=ingestion_service,
                stage_service=stage_service,
                repository_version_service=RepositoryVersionService(
                    store=RepositoryVersionStore(session=worker_session),
                ),
            )
            worker = IngestionWorker(
                session=worker_session,
                consumer=consumer,
                ingestion_service=ingestion_service,
                processor=processor,
            )

            assert await worker.run_once() is True

        # A new client represents reopening or refreshing the progress page.
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as refreshed_api_client:
            completed_response = await refreshed_api_client.get(
                f"/api/repositories/{repository_id}/ingestion",
            )

        assert completed_response.status_code == 200
        completed = completed_response.json()
        assert completed["ingestion_job"]["id"] == str(ingestion_job_id)
        assert completed["ingestion_job"]["status"] == "completed"
        assert completed["ingestion_job"]["progress"] == 100
        assert completed["ingestion_job"]["completed_at"] is not None
        assert len(completed["stages"]) == 1

        completed_stage = completed["stages"][0]
        assert completed_stage["name"] == FOUNDATION_STAGE_NAME
        assert completed_stage["position"] == 0
        assert completed_stage["status"] == "completed"
        assert completed_stage["progress"] == 100
        assert completed_stage["error_message"] is None
        assert completed_stage["completed_at"] is not None

        pending_summary = await redis_client.xpending(
            stream_name,
            group_name,
        )
        assert pending_summary["pending"] == 0
    finally:
        app.dependency_overrides.clear()

        async with async_session_factory() as cleanup_session:
            repository_store = RepositoryStore(session=cleanup_session)
            repository = await repository_store.get_by_github_id(github_id)

            if repository is not None:
                await repository_store.delete(repository)
                await cleanup_session.commit()

        await redis_client.delete(stream_name)
        await github_http_client.aclose()
        await redis_client.aclose()
