from typing import Any

import pytest
from pydantic import ValidationError

from src.github.schemas import (
    GitHubCommit,
    GitHubRepository,
)


def repository_payload() -> dict[str, Any]:
    return {
        "id": 123456789,
        "name": "trace",
        "full_name": "kumari-anushka/trace",
        "html_url": "https://github.com/kumari-anushka/trace",
        "default_branch": "main",
        "private": False,
        "archived": False,
        "disabled": False,
        "owner": {
            "login": "kumari-anushka",
        },
    }


def test_github_repository_parses_api_payload() -> None:
    repository = GitHubRepository.model_validate(
        repository_payload(),
    )

    assert repository.github_id == 123456789
    assert repository.name == "trace"
    assert repository.full_name == "kumari-anushka/trace"
    assert repository.html_url == ("https://github.com/kumari-anushka/trace")
    assert repository.default_branch == "main"
    assert repository.private is False
    assert repository.archived is False
    assert repository.disabled is False
    assert repository.owner.login == "kumari-anushka"


def test_github_repository_maps_id_to_github_id() -> None:
    payload = repository_payload()
    payload["id"] = 987654321

    repository = GitHubRepository.model_validate(payload)

    assert repository.github_id == 987654321


def test_github_repository_ignores_extra_fields() -> None:
    payload = repository_payload()
    payload["description"] = "Software intelligence platform"
    payload["forks_count"] = 42

    repository = GitHubRepository.model_validate(payload)

    assert repository.github_id == 123456789
    assert not hasattr(repository, "description")
    assert not hasattr(repository, "forks_count")


@pytest.mark.parametrize(
    "missing_field",
    [
        "id",
        "name",
        "full_name",
        "html_url",
        "default_branch",
        "private",
        "archived",
        "disabled",
        "owner",
    ],
)
def test_github_repository_rejects_missing_required_field(
    missing_field: str,
) -> None:
    payload = repository_payload()
    del payload[missing_field]

    with pytest.raises(ValidationError):
        GitHubRepository.model_validate(payload)


def test_github_repository_rejects_owner_without_login() -> None:
    payload = repository_payload()
    payload["owner"] = {}

    with pytest.raises(ValidationError):
        GitHubRepository.model_validate(payload)


def test_github_commit_parses_commit_sha() -> None:
    commit_sha = "a" * 40

    commit = GitHubCommit.model_validate(
        {
            "sha": commit_sha,
        },
    )

    assert commit.sha == commit_sha


def test_github_commit_ignores_extra_fields() -> None:
    commit = GitHubCommit.model_validate(
        {
            "sha": "b" * 40,
            "commit": {
                "message": "Initial commit",
            },
        },
    )

    assert commit.sha == "b" * 40
    assert not hasattr(commit, "commit")


def test_github_commit_rejects_missing_sha() -> None:
    with pytest.raises(ValidationError):
        GitHubCommit.model_validate({})
