from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from src.github.models import (
    GitHubCommit,
    GitHubCommitFile,
    GitHubCommitParent,
    GitHubIssue,
    GitHubPerson,
    GitHubPullRequest,
    GitHubPullRequestFile,
    GitHubPullRequestReview,
    GitHubRelease,
    SourceFile,
)
from src.graph.history import HistoricalGraphBuilder, HistoricalGraphData
from src.graph.models import RelationshipType

from .fakes import MemoryGraphRepository


class MemoryHistoricalArtifactReader:
    def __init__(self, data: HistoricalGraphData) -> None:
        self.data = data

    async def read(
        self, *, repository_id: UUID, repository_version_id: UUID
    ) -> HistoricalGraphData:
        return self.data


@pytest.mark.asyncio
async def test_builds_idempotent_historical_graph_with_supported_relations() -> None:
    now = datetime.now(UTC)
    repository_id = uuid4()
    repository_version_id = uuid4()
    alice = _person(repository_id, 101, "alice")
    bob = _person(repository_id, 102, "bob")
    issue_one = _issue(repository_id, 1, alice.id, "Broken routing", now)
    issue_three = _issue(repository_id, 3, bob.id, "Missing tests", now)
    pull_request = _pull_request(
        repository_id,
        2,
        alice.id,
        "Repair routing",
        "Fixes #1. See #3.",
        now,
    )
    parent_commit = _commit(repository_id, "a" * 40, bob.id, "Initial version", now)
    child_commit = _commit(repository_id, "b" * 40, alice.id, "Follow-up for #3", now)
    release = _release(repository_id, bob.id, child_commit.sha, now)
    source_file = SourceFile(
        id=uuid4(),
        repository_version_id=repository_version_id,
        path="src/main.py",
        blob_sha="c" * 40,
        size=20,
        mode="100644",
        file_kind="source",
        language="Python",
    )
    data = HistoricalGraphData(
        people=[alice, bob],
        issues=[issue_one, issue_three],
        pull_requests=[pull_request],
        reviews=[
            GitHubPullRequestReview(
                id=uuid4(),
                repository_id=repository_id,
                pull_request_id=pull_request.id,
                github_review_id=201,
                author_id=bob.id,
                body="Looks good",
                state="APPROVED",
                commit_sha=child_commit.sha,
                html_url="https://github.test/reviews/201",
                submitted_at=now,
            )
        ],
        commits=[parent_commit, child_commit],
        commit_parents=[
            GitHubCommitParent(commit_id=child_commit.id, parent_sha=parent_commit.sha)
        ],
        releases=[release],
        pull_request_files=[
            GitHubPullRequestFile(
                pull_request_id=pull_request.id,
                filename=source_file.path,
                status="modified",
                additions=3,
                deletions=1,
                changes=4,
                previous_filename=None,
                blob_url="https://github.test/blob/main/src/main.py",
            )
        ],
        commit_files=[
            GitHubCommitFile(
                commit_id=child_commit.id,
                filename=source_file.path,
                status="modified",
                additions=2,
                deletions=0,
                changes=2,
                previous_filename=None,
                blob_url="https://github.test/blob/main/src/main.py",
            )
        ],
        source_files=[source_file],
    )
    graph_repository = MemoryGraphRepository()
    builder = HistoricalGraphBuilder(
        graph_repository=graph_repository,
        artifact_reader=MemoryHistoricalArtifactReader(data),
    )

    first = await builder.build(
        repository_id=repository_id,
        repository_version_id=repository_version_id,
    )
    second = await builder.build(
        repository_id=repository_id,
        repository_version_id=repository_version_id,
    )

    assert first == second
    assert first.people == 2
    assert first.artifacts == 6
    assert first.files == 1
    assert first.edges == 14
    assert first.evidence == 14
    assert first.authored == 6
    assert first.reviewed == 1
    assert first.modifies == 2
    assert first.references == 2
    assert first.resolves == 1
    assert first.parent_of == 1
    assert first.release_includes == 1
    assert first.unresolved_files == 0
    assert first.unresolved_references == 0
    assert first.unresolved_parents == 0
    assert len(graph_repository.nodes) == 9
    assert len(graph_repository.edges) == 14
    assert len(graph_repository.evidence) == 14
    assert {edge.relationship_type for edge in graph_repository.edges.values()} == {
        RelationshipType.AUTHORED,
        RelationshipType.REVIEWED,
        RelationshipType.MODIFIES,
        RelationshipType.REFERENCES,
        RelationshipType.RESOLVES,
        RelationshipType.PARENT_OF,
        RelationshipType.RELEASE_INCLUDES,
    }


def _person(repository_id: UUID, github_user_id: int, login: str) -> GitHubPerson:
    return GitHubPerson(
        id=uuid4(),
        repository_id=repository_id,
        github_user_id=github_user_id,
        login=login,
        avatar_url=None,
        html_url=f"https://github.test/{login}",
        account_type="User",
    )


def _issue(
    repository_id: UUID,
    number: int,
    author_id: UUID,
    title: str,
    now: datetime,
) -> GitHubIssue:
    return GitHubIssue(
        id=uuid4(),
        repository_id=repository_id,
        github_issue_id=1_000 + number,
        number=number,
        author_id=author_id,
        title=title,
        body=None,
        state="open",
        state_reason=None,
        locked=False,
        comments_count=0,
        html_url=f"https://github.test/issues/{number}",
        created_at=now,
        updated_at=now,
        closed_at=None,
    )


def _pull_request(
    repository_id: UUID,
    number: int,
    author_id: UUID,
    title: str,
    body: str,
    now: datetime,
) -> GitHubPullRequest:
    return GitHubPullRequest(
        id=uuid4(),
        repository_id=repository_id,
        github_pull_request_id=2_000 + number,
        number=number,
        author_id=author_id,
        title=title,
        body=body,
        state="closed",
        draft=False,
        locked=False,
        html_url=f"https://github.test/pull/{number}",
        head_sha="d" * 40,
        base_sha="e" * 40,
        merge_commit_sha="b" * 40,
        created_at=now,
        updated_at=now,
        closed_at=now,
        merged_at=now,
    )


def _commit(
    repository_id: UUID,
    sha: str,
    author_id: UUID,
    message: str,
    now: datetime,
) -> GitHubCommit:
    return GitHubCommit(
        id=uuid4(),
        repository_id=repository_id,
        sha=sha,
        author_id=author_id,
        committer_id=author_id,
        git_author_name="Git Author",
        git_author_email="author@example.test",
        git_author_date=now,
        git_committer_name="Git Committer",
        git_committer_email="committer@example.test",
        git_committer_date=now,
        message=message,
        html_url=f"https://github.test/commit/{sha}",
    )


def _release(
    repository_id: UUID,
    author_id: UUID,
    target_commitish: str,
    now: datetime,
) -> GitHubRelease:
    return GitHubRelease(
        id=uuid4(),
        repository_id=repository_id,
        github_release_id=301,
        author_id=author_id,
        tag_name="v1.0.0",
        target_commitish=target_commitish,
        name="Version 1",
        body=None,
        draft=False,
        prerelease=False,
        html_url="https://github.test/releases/v1.0.0",
        created_at=now,
        published_at=now,
    )
