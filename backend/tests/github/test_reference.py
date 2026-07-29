import pytest

from src.core.exceptions import InvalidGitHubRepositoryURLError
from src.github.reference import GitHubRepositoryReference


@pytest.mark.parametrize(
    ("github_url", "expected_owner", "expected_name"),
    [
        (
            "https://github.com/kumari-anushka/trace",
            "kumari-anushka",
            "trace",
        ),
        (
            "https://github.com/kumari-anushka/trace/",
            "kumari-anushka",
            "trace",
        ),
        (
            "https://www.github.com/kumari-anushka/trace",
            "kumari-anushka",
            "trace",
        ),
        (
            "  https://github.com/kumari-anushka/trace  ",
            "kumari-anushka",
            "trace",
        ),
    ],
)
def test_from_url_returns_repository_reference(
    github_url: str,
    expected_owner: str,
    expected_name: str,
) -> None:
    reference = GitHubRepositoryReference.from_url(github_url)

    assert reference.owner == expected_owner
    assert reference.name == expected_name
    assert reference.canonical_url == (f"https://github.com/{expected_owner}/{expected_name}")


@pytest.mark.parametrize(
    "github_url",
    [
        "",
        "   ",
        "github.com/owner/repository",
        "http://github.com/owner/repository",
        "https://gitlab.com/owner/repository",
        "https://github.com/owner",
        "https://github.com/owner/repository/issues",
        "https://github.com/owner/repository/tree/main",
        "https://github.com/owner/repository.git",
        "https://github.com:443/owner/repository",
        "https://github.com/",
    ],
)
def test_from_url_rejects_invalid_repository_url(
    github_url: str,
) -> None:
    with pytest.raises(
        InvalidGitHubRepositoryURLError,
        match="Invalid GitHub repository URL",
    ):
        GitHubRepositoryReference.from_url(github_url)
