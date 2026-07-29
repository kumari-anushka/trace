from datetime import UTC, datetime
from uuid import uuid4

from src.repository_versions.models import RepositoryVersion
from src.repository_versions.schemas import RepositoryVersionResponse

COMMIT_SHA = "a" * 40


def make_repository_version() -> RepositoryVersion:
    repository_version = RepositoryVersion(
        repository_id=uuid4(),
        commit_sha=COMMIT_SHA,
        branch="main",
    )

    repository_version.id = uuid4()
    repository_version.created_at = datetime.now(UTC)

    return repository_version


def test_repository_version_response_builds_from_model() -> None:
    repository_version = make_repository_version()

    response = RepositoryVersionResponse.model_validate(
        repository_version,
    )

    assert response.id == repository_version.id
    assert response.repository_id == (repository_version.repository_id)
    assert response.commit_sha == COMMIT_SHA
    assert response.branch == "main"
    assert response.created_at == repository_version.created_at


def test_repository_version_response_serializes_values() -> None:
    repository_version = make_repository_version()

    response = RepositoryVersionResponse.model_validate(
        repository_version,
    )

    payload = response.model_dump(mode="json")

    assert payload["id"] == str(repository_version.id)
    assert payload["repository_id"] == str(
        repository_version.repository_id,
    )
    assert payload["commit_sha"] == COMMIT_SHA
    assert payload["branch"] == "main"

    serialized_created_at = datetime.fromisoformat(
        payload["created_at"].replace("Z", "+00:00"),
    )

    assert serialized_created_at == repository_version.created_at
