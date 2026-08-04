from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, TypeVar
from uuid import UUID

from sqlalchemy import ColumnElement, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.base import Base
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
from src.graph.canonical import (
    commit_key,
    evidence_key,
    file_key,
    issue_key,
    person_key,
    pull_request_key,
    release_key,
)
from src.graph.models import EntityType, EvidenceType, GraphEdge, GraphNode, RelationshipType
from src.graph.references import extract_artifact_references, reference_excerpt
from src.graph.repository import (
    GraphEdgeInput,
    GraphEvidenceInput,
    GraphNodeInput,
    GraphRepository,
)

ModelT = TypeVar("ModelT", bound=Base)


@dataclass(frozen=True, slots=True)
class HistoricalGraphData:
    people: Sequence[GitHubPerson]
    issues: Sequence[GitHubIssue]
    pull_requests: Sequence[GitHubPullRequest]
    reviews: Sequence[GitHubPullRequestReview]
    commits: Sequence[GitHubCommit]
    commit_parents: Sequence[GitHubCommitParent]
    releases: Sequence[GitHubRelease]
    pull_request_files: Sequence[GitHubPullRequestFile]
    commit_files: Sequence[GitHubCommitFile]
    source_files: Sequence[SourceFile]


@dataclass(frozen=True, slots=True)
class HistoricalGraphSummary:
    people: int
    artifacts: int
    files: int
    edges: int
    evidence: int
    authored: int
    reviewed: int
    modifies: int
    references: int
    resolves: int
    parent_of: int
    release_includes: int
    unresolved_files: int
    unresolved_references: int
    unresolved_parents: int


class HistoricalArtifactReader(Protocol):
    async def read(
        self, *, repository_id: UUID, repository_version_id: UUID
    ) -> HistoricalGraphData: ...


class PostgresHistoricalArtifactReader:
    def __init__(self, *, session: AsyncSession) -> None:
        self.session = session

    async def read(
        self, *, repository_id: UUID, repository_version_id: UUID
    ) -> HistoricalGraphData:
        people = await self._list(GitHubPerson, GitHubPerson.repository_id == repository_id)
        issues = await self._list(GitHubIssue, GitHubIssue.repository_id == repository_id)
        pull_requests = await self._list(
            GitHubPullRequest, GitHubPullRequest.repository_id == repository_id
        )
        reviews = await self._list(
            GitHubPullRequestReview,
            GitHubPullRequestReview.repository_id == repository_id,
        )
        commits = await self._list(GitHubCommit, GitHubCommit.repository_id == repository_id)
        releases = await self._list(GitHubRelease, GitHubRelease.repository_id == repository_id)
        source_files = await self._list(
            SourceFile, SourceFile.repository_version_id == repository_version_id
        )
        pull_request_ids = [pull_request.id for pull_request in pull_requests]
        commit_ids = [commit.id for commit in commits]
        pull_request_files = await self._list(
            GitHubPullRequestFile,
            GitHubPullRequestFile.pull_request_id.in_(pull_request_ids),
        )
        commit_files = await self._list(
            GitHubCommitFile,
            GitHubCommitFile.commit_id.in_(commit_ids),
        )
        commit_parents = await self._list(
            GitHubCommitParent,
            GitHubCommitParent.commit_id.in_(commit_ids),
        )
        return HistoricalGraphData(
            people=people,
            issues=issues,
            pull_requests=pull_requests,
            reviews=reviews,
            commits=commits,
            commit_parents=commit_parents,
            releases=releases,
            pull_request_files=pull_request_files,
            commit_files=commit_files,
            source_files=source_files,
        )

    async def _list(self, model: type[ModelT], condition: ColumnElement[bool]) -> Sequence[ModelT]:
        result = await self.session.execute(
            select(model).where(condition).order_by(*model.__mapper__.primary_key)
        )
        return result.scalars().all()


class HistoricalGraphBuilder:
    """Build repository-scoped GitHub history and snapshot file relationships."""

    def __init__(
        self,
        *,
        graph_repository: GraphRepository,
        artifact_reader: HistoricalArtifactReader,
    ) -> None:
        self.graph_repository = graph_repository
        self.artifact_reader = artifact_reader

    async def build(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
    ) -> HistoricalGraphSummary:
        data = await self.artifact_reader.read(
            repository_id=repository_id,
            repository_version_id=repository_version_id,
        )
        people = await self._upsert_people(repository_id, data.people)
        files = await self._upsert_files(repository_id, repository_version_id, data.source_files)
        issues = await self._upsert_issues(repository_id, data.issues)
        pull_requests = await self._upsert_pull_requests(repository_id, data.pull_requests)
        commits = await self._upsert_commits(repository_id, data.commits)
        releases = await self._upsert_releases(repository_id, data.releases)

        edge_identities: set[tuple[UUID, UUID, RelationshipType]] = set()
        evidence_count = 0
        relation_counts = {relationship: 0 for relationship in RelationshipType}
        unresolved_files = 0
        unresolved_references = 0
        unresolved_parents = 0

        async def relation(
            *,
            source: GraphNode,
            target: GraphNode,
            relationship: RelationshipType,
            provenance: dict[str, object],
            detail: object,
            excerpt: str | None = None,
            source_url: str | None = None,
            repository_version: UUID | None = None,
            evidence_type: EvidenceType = EvidenceType.PROVIDER_RELATION,
            metadata: dict[str, object] | None = None,
        ) -> None:
            nonlocal evidence_count
            identity = (source.id, target.id, relationship)
            if identity not in edge_identities:
                edge_identities.add(identity)
                relation_counts[relationship] += 1
            edge = await self.graph_repository.upsert_edge(
                GraphEdgeInput(
                    repository_id=repository_id,
                    repository_version_id=repository_version,
                    source_node_id=source.id,
                    target_node_id=target.id,
                    relationship_type=relationship,
                    provenance=provenance,
                    metadata=metadata or {},
                )
            )
            await self._upsert_relation_evidence(
                repository_id=repository_id,
                repository_version_id=repository_version_id,
                source=source,
                target=target,
                edge=edge,
                relationship=relationship,
                provenance=provenance,
                detail=detail,
                excerpt=excerpt,
                source_url=source_url,
                evidence_type=evidence_type,
                metadata=metadata or {},
            )
            evidence_count += 1

        for issue in data.issues:
            if issue.author_id in people:
                await relation(
                    source=people[issue.author_id],
                    target=issues[issue.id],
                    relationship=RelationshipType.AUTHORED,
                    provenance=_provider_provenance("github_issues", issue.id),
                    detail=issue.id,
                    excerpt=issue.title,
                    source_url=issue.html_url,
                )
        for pull_request in data.pull_requests:
            if pull_request.author_id in people:
                await relation(
                    source=people[pull_request.author_id],
                    target=pull_requests[pull_request.id],
                    relationship=RelationshipType.AUTHORED,
                    provenance=_provider_provenance("github_pull_requests", pull_request.id),
                    detail=pull_request.id,
                    excerpt=pull_request.title,
                    source_url=pull_request.html_url,
                )
        for commit in data.commits:
            if commit.author_id in people:
                await relation(
                    source=people[commit.author_id],
                    target=commits[commit.id],
                    relationship=RelationshipType.AUTHORED,
                    provenance=_provider_provenance("github_commits", commit.id),
                    detail=commit.id,
                    excerpt=commit.message[:1000],
                    source_url=commit.html_url,
                )
        for release in data.releases:
            if release.author_id in people:
                await relation(
                    source=people[release.author_id],
                    target=releases[release.id],
                    relationship=RelationshipType.AUTHORED,
                    provenance=_provider_provenance("github_releases", release.id),
                    detail=release.id,
                    excerpt=release.name or release.tag_name,
                    source_url=release.html_url,
                )
        for review in data.reviews:
            if review.author_id not in people or review.pull_request_id not in pull_requests:
                continue
            await relation(
                source=people[review.author_id],
                target=pull_requests[review.pull_request_id],
                relationship=RelationshipType.REVIEWED,
                provenance=_provider_provenance("github_pull_request_reviews", review.id),
                detail=review.id,
                excerpt=review.body or review.state,
                source_url=review.html_url,
                metadata={"state": review.state, "commit_sha": review.commit_sha},
            )

        for pull_request_file in data.pull_request_files:
            file_node = files.get(pull_request_file.filename)
            if file_node is None:
                unresolved_files += 1
                continue
            await relation(
                source=pull_requests[pull_request_file.pull_request_id],
                target=file_node,
                relationship=RelationshipType.MODIFIES,
                provenance=_provider_provenance(
                    "github_pull_request_files",
                    f"{pull_request_file.pull_request_id}:{pull_request_file.filename}",
                ),
                detail=pull_request_file.filename,
                excerpt=pull_request_file.filename,
                source_url=pull_request_file.blob_url,
                repository_version=repository_version_id,
                metadata=_change_metadata(pull_request_file),
            )
        for commit_file in data.commit_files:
            file_node = files.get(commit_file.filename)
            if file_node is None:
                unresolved_files += 1
                continue
            await relation(
                source=commits[commit_file.commit_id],
                target=file_node,
                relationship=RelationshipType.MODIFIES,
                provenance=_provider_provenance(
                    "github_commit_files",
                    f"{commit_file.commit_id}:{commit_file.filename}",
                ),
                detail=commit_file.filename,
                excerpt=commit_file.filename,
                source_url=commit_file.blob_url,
                repository_version=repository_version_id,
                metadata=_change_metadata(commit_file),
            )

        targets_by_number: dict[int, GraphNode] = {
            issue.number: issues[issue.id] for issue in data.issues
        }
        targets_by_number.update(
            {
                pull_request.number: pull_requests[pull_request.id]
                for pull_request in data.pull_requests
            }
        )
        issue_targets = {issue.number: issues[issue.id] for issue in data.issues}
        reference_sources: list[tuple[GraphNode, str, str, int | None, bool, dict[str, object]]] = [
            (
                issues[issue.id],
                f"{issue.title}\n{issue.body or ''}",
                issue.html_url,
                issue.number,
                False,
                _provider_provenance("github_issues", issue.id),
            )
            for issue in data.issues
        ]
        reference_sources.extend(
            (
                pull_requests[pull_request.id],
                f"{pull_request.title}\n{pull_request.body or ''}",
                pull_request.html_url,
                pull_request.number,
                True,
                _provider_provenance("github_pull_requests", pull_request.id),
            )
            for pull_request in data.pull_requests
        )
        reference_sources.extend(
            (
                commits[commit.id],
                commit.message,
                commit.html_url,
                None,
                True,
                _provider_provenance("github_commits", commit.id),
            )
            for commit in data.commits
        )
        reference_sources.extend(
            (
                releases[release.id],
                f"{release.name or release.tag_name}\n{release.body or ''}",
                release.html_url,
                None,
                False,
                _provider_provenance("github_releases", release.id),
            )
            for release in data.releases
        )
        for source, text, url, own_number, supports_resolution, provenance in reference_sources:
            extracted = extract_artifact_references(text, supports_resolution=supports_resolution)
            for number in sorted(extracted.referenced):
                target = targets_by_number.get(number)
                if target is None:
                    unresolved_references += 1
                    continue
                if target.id == source.id or number == own_number:
                    continue
                await relation(
                    source=source,
                    target=target,
                    relationship=RelationshipType.REFERENCES,
                    provenance=provenance,
                    detail=number,
                    excerpt=reference_excerpt(text, number),
                    source_url=url,
                    evidence_type=EvidenceType.ARTIFACT,
                )
            for number in sorted(extracted.resolved):
                target = issue_targets.get(number)
                if target is None:
                    unresolved_references += 1
                    continue
                if target.id == source.id:
                    continue
                await relation(
                    source=source,
                    target=target,
                    relationship=RelationshipType.RESOLVES,
                    provenance=provenance,
                    detail=number,
                    excerpt=reference_excerpt(text, number),
                    source_url=url,
                    evidence_type=EvidenceType.ARTIFACT,
                )

        commits_by_sha = {commit.sha: commits[commit.id] for commit in data.commits}
        for parent in data.commit_parents:
            parent_node = commits_by_sha.get(parent.parent_sha)
            child_node = commits.get(parent.commit_id)
            if parent_node is None or child_node is None:
                unresolved_parents += 1
                continue
            await relation(
                source=parent_node,
                target=child_node,
                relationship=RelationshipType.PARENT_OF,
                provenance=_provider_provenance(
                    "github_commit_parents", f"{parent.commit_id}:{parent.parent_sha}"
                ),
                detail=parent.parent_sha,
                excerpt=parent.parent_sha,
            )
        for release in data.releases:
            commit_node = commits_by_sha.get(release.target_commitish)
            if commit_node is None:
                continue
            await relation(
                source=releases[release.id],
                target=commit_node,
                relationship=RelationshipType.RELEASE_INCLUDES,
                provenance=_provider_provenance("github_releases", release.id),
                detail=release.target_commitish,
                excerpt=release.target_commitish,
                source_url=release.html_url,
            )

        return HistoricalGraphSummary(
            people=len(people),
            artifacts=len(issues) + len(pull_requests) + len(commits) + len(releases),
            files=len(files),
            edges=len(edge_identities),
            evidence=evidence_count,
            authored=relation_counts[RelationshipType.AUTHORED],
            reviewed=relation_counts[RelationshipType.REVIEWED],
            modifies=relation_counts[RelationshipType.MODIFIES],
            references=relation_counts[RelationshipType.REFERENCES],
            resolves=relation_counts[RelationshipType.RESOLVES],
            parent_of=relation_counts[RelationshipType.PARENT_OF],
            release_includes=relation_counts[RelationshipType.RELEASE_INCLUDES],
            unresolved_files=unresolved_files,
            unresolved_references=unresolved_references,
            unresolved_parents=unresolved_parents,
        )

    async def _upsert_people(
        self, repository_id: UUID, rows: Sequence[GitHubPerson]
    ) -> dict[UUID, GraphNode]:
        nodes = {}
        for row in rows:
            nodes[row.id] = await self.graph_repository.upsert_node(
                GraphNodeInput(
                    repository_id=repository_id,
                    repository_version_id=None,
                    entity_type=EntityType.PERSON,
                    canonical_key=person_key(row.github_user_id),
                    name=row.login,
                    provenance=_provider_provenance("github_people", row.id),
                    metadata={
                        "github_user_id": row.github_user_id,
                        "login": row.login,
                        "avatar_url": row.avatar_url,
                        "html_url": row.html_url,
                        "account_type": row.account_type,
                    },
                )
            )
        return nodes

    async def _upsert_files(
        self,
        repository_id: UUID,
        repository_version_id: UUID,
        rows: Sequence[SourceFile],
    ) -> dict[str, GraphNode]:
        nodes = {}
        for row in rows:
            nodes[row.path] = await self.graph_repository.upsert_node(
                GraphNodeInput(
                    repository_id=repository_id,
                    repository_version_id=repository_version_id,
                    entity_type=EntityType.FILE,
                    canonical_key=file_key(repository_id, repository_version_id, row.path),
                    name=row.path.rsplit("/", maxsplit=1)[-1],
                    provenance={
                        "kind": "provider_snapshot",
                        "provider": "github",
                        "repository_version_id": str(repository_version_id),
                        "source_file_id": str(row.id),
                        "blob_sha": row.blob_sha,
                    },
                    metadata={
                        "path": row.path,
                        "file_kind": row.file_kind,
                        "language": row.language,
                        "size": row.size,
                    },
                )
            )
        return nodes

    async def _upsert_issues(
        self, repository_id: UUID, rows: Sequence[GitHubIssue]
    ) -> dict[UUID, GraphNode]:
        nodes = {}
        for row in rows:
            nodes[row.id] = await self.graph_repository.upsert_node(
                GraphNodeInput(
                    repository_id=repository_id,
                    repository_version_id=None,
                    entity_type=EntityType.ISSUE,
                    canonical_key=issue_key(repository_id, row.number),
                    name=f"#{row.number} {row.title}",
                    description=_bounded(row.body),
                    provenance=_provider_provenance("github_issues", row.id),
                    metadata={
                        "number": row.number,
                        "state": row.state,
                        "state_reason": row.state_reason,
                        "html_url": row.html_url,
                        "created_at": _iso(row.created_at),
                        "updated_at": _iso(row.updated_at),
                        "closed_at": _iso(row.closed_at),
                    },
                )
            )
        return nodes

    async def _upsert_pull_requests(
        self, repository_id: UUID, rows: Sequence[GitHubPullRequest]
    ) -> dict[UUID, GraphNode]:
        nodes = {}
        for row in rows:
            nodes[row.id] = await self.graph_repository.upsert_node(
                GraphNodeInput(
                    repository_id=repository_id,
                    repository_version_id=None,
                    entity_type=EntityType.PULL_REQUEST,
                    canonical_key=pull_request_key(repository_id, row.number),
                    name=f"#{row.number} {row.title}",
                    description=_bounded(row.body),
                    provenance=_provider_provenance("github_pull_requests", row.id),
                    metadata={
                        "number": row.number,
                        "state": row.state,
                        "draft": row.draft,
                        "html_url": row.html_url,
                        "head_sha": row.head_sha,
                        "base_sha": row.base_sha,
                        "merge_commit_sha": row.merge_commit_sha,
                        "created_at": _iso(row.created_at),
                        "updated_at": _iso(row.updated_at),
                        "merged_at": _iso(row.merged_at),
                    },
                )
            )
        return nodes

    async def _upsert_commits(
        self, repository_id: UUID, rows: Sequence[GitHubCommit]
    ) -> dict[UUID, GraphNode]:
        nodes = {}
        for row in rows:
            nodes[row.id] = await self.graph_repository.upsert_node(
                GraphNodeInput(
                    repository_id=repository_id,
                    repository_version_id=None,
                    entity_type=EntityType.COMMIT,
                    canonical_key=commit_key(repository_id, row.sha),
                    name=f"{row.sha[:7]} {row.message.splitlines()[0]}",
                    description=_bounded(row.message),
                    provenance=_provider_provenance("github_commits", row.id),
                    metadata={
                        "sha": row.sha,
                        "html_url": row.html_url,
                        "git_author_name": row.git_author_name,
                        "git_author_date": _iso(row.git_author_date),
                        "git_committer_date": _iso(row.git_committer_date),
                    },
                )
            )
        return nodes

    async def _upsert_releases(
        self, repository_id: UUID, rows: Sequence[GitHubRelease]
    ) -> dict[UUID, GraphNode]:
        nodes = {}
        for row in rows:
            nodes[row.id] = await self.graph_repository.upsert_node(
                GraphNodeInput(
                    repository_id=repository_id,
                    repository_version_id=None,
                    entity_type=EntityType.RELEASE,
                    canonical_key=release_key(repository_id, row.github_release_id),
                    name=row.name or row.tag_name,
                    description=_bounded(row.body),
                    provenance=_provider_provenance("github_releases", row.id),
                    metadata={
                        "github_release_id": row.github_release_id,
                        "tag_name": row.tag_name,
                        "target_commitish": row.target_commitish,
                        "draft": row.draft,
                        "prerelease": row.prerelease,
                        "html_url": row.html_url,
                        "published_at": _iso(row.published_at),
                    },
                )
            )
        return nodes

    async def _upsert_relation_evidence(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        source: GraphNode,
        target: GraphNode,
        edge: GraphEdge,
        relationship: RelationshipType,
        provenance: dict[str, object],
        detail: object,
        excerpt: str | None,
        source_url: str | None,
        evidence_type: EvidenceType,
        metadata: dict[str, object],
    ) -> None:
        await self.graph_repository.upsert_evidence(
            GraphEvidenceInput(
                repository_id=repository_id,
                repository_version_id=repository_version_id,
                canonical_key=evidence_key(
                    repository_id,
                    repository_version_id,
                    source.canonical_key,
                    target.canonical_key,
                    relationship,
                    detail,
                ),
                source_node_id=source.id,
                target_edge_id=edge.id,
                evidence_type=evidence_type,
                relationship=relationship,
                excerpt=excerpt,
                source_url=source_url,
                provenance=provenance,
                metadata=metadata,
            )
        )


def _provider_provenance(table: str, record_id: object) -> dict[str, object]:
    return {"kind": "provider_artifact", "provider": "github", "table": table, "id": str(record_id)}


def _change_metadata(changed_file: GitHubPullRequestFile | GitHubCommitFile) -> dict[str, object]:
    return {
        "filename": changed_file.filename,
        "status": changed_file.status,
        "additions": changed_file.additions,
        "deletions": changed_file.deletions,
        "changes": changed_file.changes,
        "previous_filename": changed_file.previous_filename,
    }


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _bounded(value: str | None, limit: int = 2_000) -> str | None:
    return value[:limit] if value is not None else None
