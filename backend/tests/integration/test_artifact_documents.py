from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from src.db.session import async_session_factory
from src.github.models import GitHubIssue, GitHubPullRequest, GitHubRelease
from src.graph.canonical import issue_key, pull_request_key, release_key
from src.graph.models import GraphNode
from src.repositories.store import RepositoryStore
from src.repository_versions.store import RepositoryVersionStore
from src.semantic.artifacts import ArtifactDocumentBuilder, PostgresArtifactSourceReader
from src.semantic.models import Document, DocumentSourceType
from src.semantic.repository import PostgresSemanticRepository


def _artifact_node(
    repository_id: UUID,
    canonical_key: str,
    entity_type: str,
    name: str,
) -> GraphNode:
    return GraphNode(
        repository_id=repository_id,
        repository_version_id=None,
        entity_type=entity_type,
        canonical_key=canonical_key,
        name=name,
        description=None,
        knowledge_kind="deterministic",
        confidence=1.0,
        provenance={"provider": "github"},
        details={},
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_artifact_documents_are_idempotent_linked_and_pruned() -> None:
    suffix = uuid4().hex
    now = datetime.now(UTC)
    async with async_session_factory() as session:
        repository_store = RepositoryStore(session=session)
        repository = await repository_store.create(
            github_id=uuid4().int % (2**63 - 1),
            github_url=f"https://github.com/acme/artifacts-{suffix}",
            owner="acme",
            name=f"artifacts-{suffix}",
            default_branch="main",
        )
        version = await RepositoryVersionStore(session=session).create(
            repository_id=repository.id,
            commit_sha="e" * 40,
            branch="main",
        )
        issue_body = "# Context\n\n" + ("graph evidence " * 220)
        issue = GitHubIssue(
            repository_id=repository.id,
            github_issue_id=1001,
            number=12,
            title="Explain graph evidence",
            body=issue_body,
            state="open",
            state_reason=None,
            locked=False,
            comments_count=4,
            html_url="https://github.com/acme/trace/issues/12",
            created_at=now,
            updated_at=now,
            closed_at=None,
        )
        pull_request = GitHubPullRequest(
            repository_id=repository.id,
            github_pull_request_id=2001,
            number=21,
            title="Add graph evidence",
            body=None,
            state="closed",
            draft=False,
            locked=False,
            html_url="https://github.com/acme/trace/pull/21",
            head_sha="a" * 40,
            base_sha="b" * 40,
            merge_commit_sha="c" * 40,
            created_at=now,
            updated_at=now,
            closed_at=now,
            merged_at=now,
        )
        release = GitHubRelease(
            repository_id=repository.id,
            github_release_id=3001,
            tag_name="v1.0.0",
            target_commitish=version.commit_sha,
            name="Trace 1.0",
            body="Architecture explorer release notes.",
            draft=False,
            prerelease=False,
            html_url="https://github.com/acme/trace/releases/tag/v1.0.0",
            created_at=now,
            published_at=now,
        )
        issue_node = _artifact_node(
            repository.id,
            issue_key(repository.id, issue.number),
            "issue",
            issue.title,
        )
        pull_request_node = _artifact_node(
            repository.id,
            pull_request_key(repository.id, pull_request.number),
            "pull_request",
            pull_request.title,
        )
        release_node = _artifact_node(
            repository.id,
            release_key(repository.id, release.github_release_id),
            "release",
            release.name or release.tag_name,
        )
        session.add_all([issue, pull_request, release, issue_node, pull_request_node, release_node])
        await session.commit()

        try:
            builder = ArtifactDocumentBuilder(
                semantic_repository=PostgresSemanticRepository(session=session),
                source_reader=PostgresArtifactSourceReader(session=session),
            )
            first_summary = await builder.build(
                repository_id=repository.id,
                repository_version_id=version.id,
            )
            await session.commit()
            second_summary = await builder.build(
                repository_id=repository.id,
                repository_version_id=version.id,
            )
            await session.commit()

            assert first_summary.issues == 1
            assert first_summary.pull_requests == 1
            assert first_summary.releases == 1
            assert first_summary.chunks == 4
            assert second_summary.chunks == first_summary.chunks
            documents = (
                (
                    await session.execute(
                        select(Document)
                        .where(Document.repository_id == repository.id)
                        .order_by(Document.source_type, Document.chunk_index)
                    )
                )
                .scalars()
                .all()
            )
            assert len(documents) == 4
            assert all(document.source_node_id is not None for document in documents)
            issue_documents = [
                document
                for document in documents
                if document.source_type == DocumentSourceType.ISSUE.value
            ]
            assert len(issue_documents) == 2
            assert all(document.details["number"] == 12 for document in issue_documents)
            assert all(document.details["content_field"] == "body" for document in issue_documents)
            for document in issue_documents:
                assert document.start_offset is not None
                assert document.end_offset is not None
                assert document.content == issue_body[document.start_offset : document.end_offset]
            pull_request_document = next(
                document
                for document in documents
                if document.source_type == DocumentSourceType.PULL_REQUEST.value
            )
            assert pull_request_document.content == pull_request.title
            assert pull_request_document.details["content_field"] == "title"

            issue.body = "A concise evidence request."
            await session.delete(release)
            await session.commit()
            summary = await builder.build(
                repository_id=repository.id,
                repository_version_id=version.id,
            )
            await session.commit()

            document_count = (
                await session.execute(
                    select(func.count())
                    .select_from(Document)
                    .where(Document.repository_id == repository.id)
                )
            ).scalar_one()
            assert summary.issues == 1
            assert summary.releases == 0
            assert summary.chunks == 2
            assert summary.stale_documents == 2
            assert document_count == 2
        finally:
            await repository_store.delete(repository)
            await session.commit()
