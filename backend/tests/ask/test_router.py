from typing import cast
from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.ask.dependencies import get_repository_query_service
from src.ask.models import (
    AnswerClaim,
    QueryResult,
    RetrievalMode,
    RetrievedEvidence,
)
from src.ask.router import router
from src.ask.service import RepositoryQueryService


def test_repository_query_endpoint_returns_grounded_contract() -> None:
    repository_id = uuid4()
    version_id = uuid4()
    service = AsyncMock(spec=RepositoryQueryService)
    service.query.return_value = QueryResult(
        repository_id=repository_id,
        repository_version_id=version_id,
        question="Why did this change?",
        answer="The change was recorded.",
        claims=(AnswerClaim("The change was recorded.", ("doc:one",)),),
        citations=(
            RetrievedEvidence(
                id="doc:one",
                title="Pull request 4",
                content="Recorded rationale",
                score=0.2,
                modes=(RetrievalMode.METADATA, RetrievalMode.VECTOR),
                source_type="pull_request",
                source_url="https://github.com/example/repo/pull/4",
            ),
        ),
        limitations=("Snapshot only.",),
        retrieval_modes=(RetrievalMode.GRAPH, RetrievalMode.METADATA),
        grounded=True,
    )
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_repository_query_service] = lambda: cast(
        RepositoryQueryService, service
    )

    with TestClient(app) as client:
        response = client.post(
            f"/api/repositories/{repository_id}/query",
            json={"question": "Why did this change?"},
        )

    assert response.status_code == 200
    assert response.json()["grounded"] is True
    assert response.json()["citations"][0]["id"] == "doc:one"
    service.query.assert_awaited_once_with(
        repository_id=repository_id, question="Why did this change?"
    )


def test_repository_query_rejects_blank_question() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_repository_query_service] = lambda: AsyncMock(
        spec=RepositoryQueryService
    )

    with TestClient(app) as client:
        response = client.post(f"/api/repositories/{uuid4()}/query", json={"question": ""})

    assert response.status_code == 422
