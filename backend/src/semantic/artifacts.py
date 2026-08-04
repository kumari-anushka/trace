from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.github.models import GitHubIssue, GitHubPullRequest, GitHubRelease
from src.graph.canonical import issue_key, pull_request_key, release_key
from src.graph.models import GraphNode
from src.semantic.documentation import DOCUMENTATION_CHUNKER_VERSION, chunk_documentation
from src.semantic.models import DocumentSourceType
from src.semantic.repository import DocumentInput, SemanticRepository

ARTIFACT_CHUNKER_VERSION = f"artifact-{DOCUMENTATION_CHUNKER_VERSION}"


@dataclass(frozen=True, slots=True)
class ArtifactDocumentSource:
    id: UUID
    source_type: DocumentSourceType
    source_key: str
    title: str
    content: str
    content_field: str
    source_url: str
    provider_table: str
    metadata: dict[str, object]
    source_node_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class ArtifactDocumentSummary:
    issues: int
    pull_requests: int
    releases: int
    chunks: int
    characters: int
    empty_artifacts: int
    stale_documents: int
    chunker_version: str = ARTIFACT_CHUNKER_VERSION


class ArtifactSourceReader(Protocol):
    async def list_artifact_sources(
        self, repository_id: UUID
    ) -> Sequence[ArtifactDocumentSource]: ...


class PostgresArtifactSourceReader:
    def __init__(self, *, session: AsyncSession) -> None:
        self.session = session

    async def list_artifact_sources(self, repository_id: UUID) -> Sequence[ArtifactDocumentSource]:
        issues = (
            (
                await self.session.execute(
                    select(GitHubIssue)
                    .where(GitHubIssue.repository_id == repository_id)
                    .order_by(GitHubIssue.number)
                )
            )
            .scalars()
            .all()
        )
        pull_requests = (
            (
                await self.session.execute(
                    select(GitHubPullRequest)
                    .where(GitHubPullRequest.repository_id == repository_id)
                    .order_by(GitHubPullRequest.number)
                )
            )
            .scalars()
            .all()
        )
        releases = (
            (
                await self.session.execute(
                    select(GitHubRelease)
                    .where(GitHubRelease.repository_id == repository_id)
                    .order_by(GitHubRelease.created_at, GitHubRelease.github_release_id)
                )
            )
            .scalars()
            .all()
        )

        canonical_keys = {
            *(issue_key(repository_id, issue.number) for issue in issues),
            *(
                pull_request_key(repository_id, pull_request.number)
                for pull_request in pull_requests
            ),
            *(release_key(repository_id, release.github_release_id) for release in releases),
        }
        node_ids_by_key: dict[str, UUID] = {}
        if canonical_keys:
            node_rows = await self.session.execute(
                select(GraphNode.canonical_key, GraphNode.id).where(
                    GraphNode.repository_id == repository_id,
                    GraphNode.canonical_key.in_(canonical_keys),
                )
            )
            node_ids_by_key = {canonical_key: node_id for canonical_key, node_id in node_rows.all()}

        sources: list[ArtifactDocumentSource] = []
        sources.extend(
            ArtifactDocumentSource(
                id=issue.id,
                source_type=DocumentSourceType.ISSUE,
                source_key=f"issue:{issue.number}",
                title=f"#{issue.number} {issue.title}",
                content=issue.body if issue.body and issue.body.strip() else issue.title,
                content_field="body" if issue.body and issue.body.strip() else "title",
                source_url=issue.html_url,
                provider_table="github_issues",
                source_node_id=node_ids_by_key.get(issue_key(repository_id, issue.number)),
                metadata={
                    "github_issue_id": issue.github_issue_id,
                    "number": issue.number,
                    "state": issue.state,
                    "state_reason": issue.state_reason,
                    "locked": issue.locked,
                    "comments_count": issue.comments_count,
                    "created_at": _iso(issue.created_at),
                    "updated_at": _iso(issue.updated_at),
                    "closed_at": _iso(issue.closed_at),
                },
            )
            for issue in issues
        )
        sources.extend(
            ArtifactDocumentSource(
                id=pull_request.id,
                source_type=DocumentSourceType.PULL_REQUEST,
                source_key=f"pull_request:{pull_request.number}",
                title=f"#{pull_request.number} {pull_request.title}",
                content=(
                    pull_request.body
                    if pull_request.body and pull_request.body.strip()
                    else pull_request.title
                ),
                content_field=(
                    "body" if pull_request.body and pull_request.body.strip() else "title"
                ),
                source_url=pull_request.html_url,
                provider_table="github_pull_requests",
                source_node_id=node_ids_by_key.get(
                    pull_request_key(repository_id, pull_request.number)
                ),
                metadata={
                    "github_pull_request_id": pull_request.github_pull_request_id,
                    "number": pull_request.number,
                    "state": pull_request.state,
                    "draft": pull_request.draft,
                    "locked": pull_request.locked,
                    "head_sha": pull_request.head_sha,
                    "base_sha": pull_request.base_sha,
                    "merge_commit_sha": pull_request.merge_commit_sha,
                    "created_at": _iso(pull_request.created_at),
                    "updated_at": _iso(pull_request.updated_at),
                    "closed_at": _iso(pull_request.closed_at),
                    "merged_at": _iso(pull_request.merged_at),
                },
            )
            for pull_request in pull_requests
        )
        sources.extend(
            ArtifactDocumentSource(
                id=release.id,
                source_type=DocumentSourceType.RELEASE_NOTE,
                source_key=f"release:{release.github_release_id}",
                title=release.name or release.tag_name,
                content=release.body if release.body and release.body.strip() else release.tag_name,
                content_field="body" if release.body and release.body.strip() else "tag_name",
                source_url=release.html_url,
                provider_table="github_releases",
                source_node_id=node_ids_by_key.get(
                    release_key(repository_id, release.github_release_id)
                ),
                metadata={
                    "github_release_id": release.github_release_id,
                    "tag_name": release.tag_name,
                    "target_commitish": release.target_commitish,
                    "name": release.name,
                    "draft": release.draft,
                    "prerelease": release.prerelease,
                    "created_at": _iso(release.created_at),
                    "published_at": _iso(release.published_at),
                },
            )
            for release in releases
        )
        return sources


class ArtifactDocumentBuilder:
    def __init__(
        self,
        *,
        semantic_repository: SemanticRepository,
        source_reader: ArtifactSourceReader,
    ) -> None:
        self.semantic_repository = semantic_repository
        self.source_reader = source_reader

    async def build(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
    ) -> ArtifactDocumentSummary:
        sources = await self.source_reader.list_artifact_sources(repository_id)
        retained_keys: dict[DocumentSourceType, list[str]] = {
            source_type: [] for source_type in _ARTIFACT_SOURCE_TYPES
        }
        counts = {source_type: 0 for source_type in _ARTIFACT_SOURCE_TYPES}
        chunk_count = 0
        character_count = 0
        empty_artifacts = 0

        for source in sources:
            counts[source.source_type] += 1
            chunks = chunk_documentation(source.content)
            if not chunks:
                empty_artifacts += 1
                continue
            source_content_hash = sha256(source.content.encode()).hexdigest()
            for chunk_index, chunk in enumerate(chunks):
                canonical_key = _artifact_document_key(
                    repository_id=repository_id,
                    repository_version_id=repository_version_id,
                    source_type=source.source_type,
                    source_key=source.source_key,
                    chunk_index=chunk_index,
                )
                retained_keys[source.source_type].append(canonical_key)
                await self.semantic_repository.upsert_document(
                    DocumentInput(
                        repository_id=repository_id,
                        repository_version_id=repository_version_id,
                        source_node_id=source.source_node_id,
                        source_type=source.source_type,
                        source_key=source.source_key,
                        canonical_key=canonical_key,
                        title=source.title,
                        content=chunk.content,
                        chunk_index=chunk_index,
                        start_offset=chunk.start_offset,
                        end_offset=chunk.end_offset,
                        start_line=chunk.start_line,
                        end_line=chunk.end_line,
                        source_url=source.source_url,
                        provenance={
                            "kind": "artifact_chunk",
                            "provider": "github_api",
                            "provider_table": source.provider_table,
                            "source_record_id": str(source.id),
                            "source_content_hash": source_content_hash,
                            "chunker": ARTIFACT_CHUNKER_VERSION,
                        },
                        metadata={
                            **source.metadata,
                            "content_field": source.content_field,
                            "source_content_hash": source_content_hash,
                            "chunker_version": ARTIFACT_CHUNKER_VERSION,
                            "heading": chunk.heading,
                            "start_line": chunk.start_line,
                            "end_line": chunk.end_line,
                            "start_offset": chunk.start_offset,
                            "end_offset": chunk.end_offset,
                        },
                    )
                )
                chunk_count += 1
                character_count += len(chunk.content)

        stale_documents = 0
        for source_type in _ARTIFACT_SOURCE_TYPES:
            stale_documents += await self.semantic_repository.prune_documents(
                repository_id=repository_id,
                repository_version_id=repository_version_id,
                source_type=source_type,
                retained_canonical_keys=retained_keys[source_type],
            )
        return ArtifactDocumentSummary(
            issues=counts[DocumentSourceType.ISSUE],
            pull_requests=counts[DocumentSourceType.PULL_REQUEST],
            releases=counts[DocumentSourceType.RELEASE_NOTE],
            chunks=chunk_count,
            characters=character_count,
            empty_artifacts=empty_artifacts,
            stale_documents=stale_documents,
        )


_ARTIFACT_SOURCE_TYPES = (
    DocumentSourceType.ISSUE,
    DocumentSourceType.PULL_REQUEST,
    DocumentSourceType.RELEASE_NOTE,
)


def _artifact_document_key(
    *,
    repository_id: UUID,
    repository_version_id: UUID,
    source_type: DocumentSourceType,
    source_key: str,
    chunk_index: int,
) -> str:
    identity = f"{source_type.value}\0{source_key}\0{chunk_index}\0{ARTIFACT_CHUNKER_VERSION}"
    digest = sha256(identity.encode()).hexdigest()
    return f"repo:{repository_id}:snapshot:{repository_version_id}:artifact-chunk:{digest}"


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None
