from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from src.db.session import async_session_factory
from src.github.models import (
    GitHubCommit,
    GitHubCommitFile,
    GitHubIssue,
    GitHubPerson,
    GitHubPullRequest,
    GitHubPullRequestFile,
    GitHubPullRequestReview,
    GitHubRelease,
    SourceFile,
)
from src.graph.history import HistoricalGraphBuilder, PostgresHistoricalArtifactReader
from src.graph.models import GraphEdge, GraphEvidence, GraphNode
from src.graph.repository import PostgresGraphRepository
from src.repositories.store import RepositoryStore
from src.repository_versions.store import RepositoryVersionStore


@pytest.mark.integration
@pytest.mark.asyncio
async def test_historical_graph_persists_idempotent_provider_relations() -> None:
    now = datetime.now(UTC)
    suffix = uuid4().hex
    async with async_session_factory() as session:
        repository_store = RepositoryStore(session=session)
        repository = await repository_store.create(
            github_id=uuid4().int % (2**63 - 1),
            github_url=f"https://github.com/acme/history-{suffix}",
            owner="acme",
            name=f"history-{suffix}",
            default_branch="main",
        )
        version = await RepositoryVersionStore(session=session).create(
            repository_id=repository.id,
            commit_sha="8" * 40,
            branch="main",
        )
        person = GitHubPerson(
            repository_id=repository.id,
            github_user_id=501,
            login="octocat",
            avatar_url=None,
            html_url="https://github.test/octocat",
            account_type="User",
        )
        source_file = SourceFile(
            repository_version_id=version.id,
            path="src/main.py",
            blob_sha="7" * 40,
            size=20,
            mode="100644",
            file_kind="source",
            language="Python",
        )
        session.add_all([person, source_file])
        await session.flush()

        issue = GitHubIssue(
            repository_id=repository.id,
            github_issue_id=601,
            number=1,
            author_id=person.id,
            title="Broken routing",
            body=None,
            state="closed",
            state_reason="completed",
            locked=False,
            comments_count=0,
            html_url="https://github.test/issues/1",
            created_at=now,
            updated_at=now,
            closed_at=now,
        )
        pull_request = GitHubPullRequest(
            repository_id=repository.id,
            github_pull_request_id=602,
            number=2,
            author_id=person.id,
            title="Repair routing",
            body="Closes #1",
            state="closed",
            draft=False,
            locked=False,
            html_url="https://github.test/pull/2",
            head_sha="6" * 40,
            base_sha="5" * 40,
            merge_commit_sha="4" * 40,
            created_at=now,
            updated_at=now,
            closed_at=now,
            merged_at=now,
        )
        commit = GitHubCommit(
            repository_id=repository.id,
            sha="4" * 40,
            author_id=person.id,
            committer_id=person.id,
            git_author_name="Octo Cat",
            git_author_email="octo@example.test",
            git_author_date=now,
            git_committer_name="Octo Cat",
            git_committer_email="octo@example.test",
            git_committer_date=now,
            message="Repair routing",
            html_url=f"https://github.test/commit/{'4' * 40}",
        )
        release = GitHubRelease(
            repository_id=repository.id,
            github_release_id=603,
            author_id=person.id,
            tag_name="v1.0.0",
            target_commitish=commit.sha,
            name="Version 1",
            body=None,
            draft=False,
            prerelease=False,
            html_url="https://github.test/releases/v1.0.0",
            created_at=now,
            published_at=now,
        )
        session.add_all([issue, pull_request, commit, release])
        await session.flush()
        session.add_all(
            [
                GitHubPullRequestReview(
                    repository_id=repository.id,
                    pull_request_id=pull_request.id,
                    github_review_id=604,
                    author_id=person.id,
                    body="Approved",
                    state="APPROVED",
                    commit_sha=commit.sha,
                    html_url="https://github.test/reviews/604",
                    submitted_at=now,
                ),
                GitHubPullRequestFile(
                    pull_request_id=pull_request.id,
                    filename=source_file.path,
                    status="modified",
                    additions=3,
                    deletions=1,
                    changes=4,
                    previous_filename=None,
                    blob_url="https://github.test/blob/main/src/main.py",
                ),
                GitHubCommitFile(
                    commit_id=commit.id,
                    filename=source_file.path,
                    status="modified",
                    additions=3,
                    deletions=1,
                    changes=4,
                    previous_filename=None,
                    blob_url="https://github.test/blob/main/src/main.py",
                ),
            ]
        )
        await session.commit()

        try:
            graph_repository = PostgresGraphRepository(session=session)
            builder = HistoricalGraphBuilder(
                graph_repository=graph_repository,
                artifact_reader=PostgresHistoricalArtifactReader(session=session),
            )
            for _ in range(2):
                summary = await builder.build(
                    repository_id=repository.id,
                    repository_version_id=version.id,
                )
                await session.commit()

            assert summary.people == 1
            assert summary.artifacts == 4
            assert summary.files == 1
            assert summary.edges == 9
            assert summary.evidence == 9
            assert summary.authored == 4
            assert summary.reviewed == 1
            assert summary.modifies == 2
            assert summary.resolves == 1
            assert summary.release_includes == 1

            for model, expected in (
                (GraphNode, 6),
                (GraphEdge, 9),
                (GraphEvidence, 9),
            ):
                count = (
                    await session.execute(
                        select(func.count())
                        .select_from(model)
                        .where(model.repository_id == repository.id)
                    )
                ).scalar_one()
                assert count == expected

            snapshot = await graph_repository.subgraph(
                repository_id=repository.id,
                repository_version_id=version.id,
                limit=20,
            )
            assert len(snapshot.nodes) == 6
            assert len(snapshot.edges) == 9
        finally:
            await repository_store.delete(repository)
            await session.commit()
