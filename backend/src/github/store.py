from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast
from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.github.classification import classify_source_file, normalize_repository_path
from src.github.models import (
    GitHubCommit as GitHubCommitModel,
)
from src.github.models import (
    GitHubCommitFile,
    GitHubCommitParent,
    GitHubIssueLabel,
    GitHubPerson,
    GitHubPullRequestFile,
    GitHubPullRequestLabel,
    GitHubPullRequestReview,
    IngestionArtifactSnapshot,
    SourceFile,
)
from src.github.models import (
    GitHubContributor as GitHubContributorModel,
)
from src.github.models import (
    GitHubIssue as GitHubIssueModel,
)
from src.github.models import (
    GitHubLabel as GitHubLabelModel,
)
from src.github.models import (
    GitHubPullRequest as GitHubPullRequestModel,
)
from src.github.models import (
    GitHubRelease as GitHubReleaseModel,
)
from src.github.schemas import (
    GitHubChangedFile,
    GitHubCommit,
    GitHubContributor,
    GitHubIssue,
    GitHubLabel,
    GitHubOwner,
    GitHubPullRequest,
    GitHubRelease,
    GitHubReview,
    GitHubTree,
)


class GitHubArtifactStore:
    def __init__(self, *, session: AsyncSession) -> None:
        self.session = session
        self._people: dict[tuple[UUID, int], UUID] = {}
        self._labels: dict[tuple[UUID, int], UUID] = {}

    async def replace_source_tree(
        self,
        *,
        repository_version_id: UUID,
        tree: GitHubTree,
    ) -> dict[str, int]:
        entries: list[dict[str, object]] = []
        counts: dict[str, int] = {}

        for tree_entry in tree.tree:
            if tree_entry.entry_type != "blob":
                continue
            path = normalize_repository_path(tree_entry.path)
            file_kind, language = classify_source_file(path)
            counts[file_kind.value] = counts.get(file_kind.value, 0) + 1
            entries.append(
                {
                    "repository_version_id": repository_version_id,
                    "path": path,
                    "blob_sha": tree_entry.sha,
                    "size": tree_entry.size,
                    "mode": tree_entry.mode,
                    "file_kind": file_kind.value,
                    "language": language,
                }
            )

        if entries:
            statement = insert(SourceFile).values(entries)
            await self.session.execute(
                statement.on_conflict_do_update(
                    index_elements=[SourceFile.repository_version_id, SourceFile.path],
                    set_={
                        "blob_sha": statement.excluded.blob_sha,
                        "size": statement.excluded.size,
                        "mode": statement.excluded.mode,
                        "file_kind": statement.excluded.file_kind,
                        "language": statement.excluded.language,
                    },
                )
            )

        current_paths = [entry["path"] for entry in entries]
        stale_files = delete(SourceFile).where(
            SourceFile.repository_version_id == repository_version_id
        )
        if current_paths:
            stale_files = stale_files.where(SourceFile.path.not_in(current_paths))
        await self.session.execute(stale_files)
        return {"files": len(entries), **counts}

    async def persist_artifacts(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        labels: Sequence[GitHubLabel],
        issues: Sequence[GitHubIssue],
        pull_requests: Sequence[GitHubPullRequest],
        pull_request_files: Mapping[int, Sequence[GitHubChangedFile]],
        pull_request_reviews: Mapping[int, Sequence[GitHubReview]],
        commits: Sequence[GitHubCommit],
        releases: Sequence[GitHubRelease],
        contributors: Sequence[GitHubContributor],
        bounds: dict[str, object],
    ) -> dict[str, object]:
        for label in labels:
            await self._upsert_label(repository_id, label)

        review_count = 0
        pull_request_file_count = 0
        for issue in issues:
            await self._upsert_issue(repository_id, issue)

        for pull_request in pull_requests:
            pull_request_id = await self._upsert_pull_request(repository_id, pull_request)
            files = pull_request_files.get(pull_request.number, ())
            reviews = pull_request_reviews.get(pull_request.number, ())
            await self._replace_pull_request_files(pull_request_id, files)
            await self._replace_reviews(repository_id, pull_request_id, reviews)
            pull_request_file_count += len(files)
            review_count += len(reviews)

        commit_file_count = 0
        for commit in commits:
            commit_id = await self._upsert_commit(repository_id, commit)
            await self._replace_commit_relations(commit_id, commit)
            commit_file_count += len(commit.files)

        for release in releases:
            await self._upsert_release(repository_id, release)

        for contributor in contributors:
            person_id = await self._upsert_person(repository_id, contributor)
            if person_id is None:
                continue
            statement = insert(GitHubContributorModel).values(
                repository_id=repository_id,
                person_id=person_id,
                contributions=contributor.contributions,
            )
            await self.session.execute(
                statement.on_conflict_do_update(
                    index_elements=[
                        GitHubContributorModel.repository_id,
                        GitHubContributorModel.person_id,
                    ],
                    set_={"contributions": statement.excluded.contributions},
                )
            )

        snapshot_statement = insert(IngestionArtifactSnapshot).values(
            repository_version_id=repository_version_id,
            bounds=bounds,
        )
        await self.session.execute(
            snapshot_statement.on_conflict_do_update(
                index_elements=[IngestionArtifactSnapshot.repository_version_id],
                set_={"bounds": snapshot_statement.excluded.bounds},
            )
        )

        return {
            "labels": len(labels),
            "issues": len(issues),
            "pull_requests": len(pull_requests),
            "pull_request_files": pull_request_file_count,
            "reviews": review_count,
            "commits": len(commits),
            "commit_files": commit_file_count,
            "releases": len(releases),
            "contributors": len(contributors),
        }

    async def _upsert_person(self, repository_id: UUID, person: GitHubOwner | None) -> UUID | None:
        if person is None or person.github_id <= 0:
            return None
        cache_key = (repository_id, person.github_id)
        cached = self._people.get(cache_key)
        if cached is not None:
            return cached
        person_id = await self._upsert_returning_id(
            GitHubPerson,
            {
                "repository_id": repository_id,
                "github_user_id": person.github_id,
                "login": person.login,
                "avatar_url": person.avatar_url,
                "html_url": person.html_url,
                "account_type": person.account_type,
            },
            ["repository_id", "github_user_id"],
            ["login", "avatar_url", "html_url", "account_type"],
        )
        self._people[cache_key] = person_id
        return person_id

    async def _upsert_label(self, repository_id: UUID, label: GitHubLabel) -> UUID:
        cache_key = (repository_id, label.github_id)
        cached = self._labels.get(cache_key)
        if cached is not None:
            return cached
        label_id = await self._upsert_returning_id(
            GitHubLabelModel,
            {
                "repository_id": repository_id,
                "github_label_id": label.github_id,
                "name": label.name,
                "color": label.color,
                "description": label.description,
            },
            ["repository_id", "github_label_id"],
            ["name", "color", "description"],
        )
        self._labels[cache_key] = label_id
        return label_id

    async def _upsert_issue(self, repository_id: UUID, issue: GitHubIssue) -> UUID:
        author_id = await self._upsert_person(repository_id, issue.user)
        issue_id = await self._upsert_returning_id(
            GitHubIssueModel,
            {
                "repository_id": repository_id,
                "github_issue_id": issue.github_id,
                "number": issue.number,
                "author_id": author_id,
                "title": issue.title,
                "body": issue.body,
                "state": issue.state,
                "state_reason": issue.state_reason,
                "locked": issue.locked,
                "comments_count": issue.comments,
                "html_url": issue.html_url,
                "created_at": issue.created_at,
                "updated_at": issue.updated_at,
                "closed_at": issue.closed_at,
            },
            ["repository_id", "github_issue_id"],
            [
                "number",
                "author_id",
                "title",
                "body",
                "state",
                "state_reason",
                "locked",
                "comments_count",
                "html_url",
                "updated_at",
                "closed_at",
            ],
        )
        await self.session.execute(
            delete(GitHubIssueLabel).where(GitHubIssueLabel.issue_id == issue_id)
        )
        for label in issue.labels:
            label_id = await self._upsert_label(repository_id, label)
            await self.session.execute(
                insert(GitHubIssueLabel)
                .values(issue_id=issue_id, label_id=label_id)
                .on_conflict_do_nothing()
            )
        return issue_id

    async def _upsert_pull_request(
        self, repository_id: UUID, pull_request: GitHubPullRequest
    ) -> UUID:
        author_id = await self._upsert_person(repository_id, pull_request.user)
        pull_request_id = await self._upsert_returning_id(
            GitHubPullRequestModel,
            {
                "repository_id": repository_id,
                "github_pull_request_id": pull_request.github_id,
                "number": pull_request.number,
                "author_id": author_id,
                "title": pull_request.title,
                "body": pull_request.body,
                "state": pull_request.state,
                "draft": pull_request.draft,
                "locked": pull_request.locked,
                "html_url": pull_request.html_url,
                "head_sha": pull_request.head.sha,
                "base_sha": pull_request.base.sha,
                "merge_commit_sha": pull_request.merge_commit_sha,
                "created_at": pull_request.created_at,
                "updated_at": pull_request.updated_at,
                "closed_at": pull_request.closed_at,
                "merged_at": pull_request.merged_at,
            },
            ["repository_id", "github_pull_request_id"],
            [
                "number",
                "author_id",
                "title",
                "body",
                "state",
                "draft",
                "locked",
                "html_url",
                "head_sha",
                "base_sha",
                "merge_commit_sha",
                "updated_at",
                "closed_at",
                "merged_at",
            ],
        )
        await self.session.execute(
            delete(GitHubPullRequestLabel).where(
                GitHubPullRequestLabel.pull_request_id == pull_request_id
            )
        )
        for label in pull_request.labels:
            label_id = await self._upsert_label(repository_id, label)
            await self.session.execute(
                insert(GitHubPullRequestLabel)
                .values(pull_request_id=pull_request_id, label_id=label_id)
                .on_conflict_do_nothing()
            )
        return pull_request_id

    async def _replace_pull_request_files(
        self, pull_request_id: UUID, files: Sequence[GitHubChangedFile]
    ) -> None:
        await self.session.execute(
            delete(GitHubPullRequestFile).where(
                GitHubPullRequestFile.pull_request_id == pull_request_id
            )
        )
        for changed_file in files:
            await self.session.execute(
                insert(GitHubPullRequestFile).values(
                    pull_request_id=pull_request_id,
                    **self._changed_file_values(changed_file),
                )
            )

    async def _replace_reviews(
        self,
        repository_id: UUID,
        pull_request_id: UUID,
        reviews: Sequence[GitHubReview],
    ) -> None:
        for review in reviews:
            author_id = await self._upsert_person(repository_id, review.user)
            await self._upsert_returning_id(
                GitHubPullRequestReview,
                {
                    "repository_id": repository_id,
                    "pull_request_id": pull_request_id,
                    "github_review_id": review.github_id,
                    "author_id": author_id,
                    "body": review.body,
                    "state": review.state,
                    "commit_sha": review.commit_id,
                    "html_url": review.html_url,
                    "submitted_at": review.submitted_at,
                },
                ["repository_id", "github_review_id"],
                [
                    "pull_request_id",
                    "author_id",
                    "body",
                    "state",
                    "commit_sha",
                    "html_url",
                    "submitted_at",
                ],
            )

    async def _upsert_commit(self, repository_id: UUID, commit: GitHubCommit) -> UUID:
        author_id = await self._upsert_person(repository_id, commit.author)
        committer_id = await self._upsert_person(repository_id, commit.committer)
        git_author = commit.commit.author
        git_committer = commit.commit.committer
        return await self._upsert_returning_id(
            GitHubCommitModel,
            {
                "repository_id": repository_id,
                "sha": commit.sha,
                "author_id": author_id,
                "committer_id": committer_id,
                "git_author_name": git_author.name if git_author else None,
                "git_author_email": git_author.email if git_author else None,
                "git_author_date": git_author.date if git_author else None,
                "git_committer_name": git_committer.name if git_committer else None,
                "git_committer_email": git_committer.email if git_committer else None,
                "git_committer_date": git_committer.date if git_committer else None,
                "message": commit.commit.message,
                "html_url": commit.html_url,
            },
            ["repository_id", "sha"],
            [
                "author_id",
                "committer_id",
                "git_author_name",
                "git_author_email",
                "git_author_date",
                "git_committer_name",
                "git_committer_email",
                "git_committer_date",
                "message",
                "html_url",
            ],
        )

    async def _replace_commit_relations(self, commit_id: UUID, commit: GitHubCommit) -> None:
        await self.session.execute(
            delete(GitHubCommitParent).where(GitHubCommitParent.commit_id == commit_id)
        )
        await self.session.execute(
            delete(GitHubCommitFile).where(GitHubCommitFile.commit_id == commit_id)
        )
        for parent in commit.parents:
            await self.session.execute(
                insert(GitHubCommitParent).values(commit_id=commit_id, parent_sha=parent.sha)
            )
        for changed_file in commit.files:
            await self.session.execute(
                insert(GitHubCommitFile).values(
                    commit_id=commit_id,
                    **self._changed_file_values(changed_file),
                )
            )

    async def _upsert_release(self, repository_id: UUID, release: GitHubRelease) -> UUID:
        author_id = await self._upsert_person(repository_id, release.author)
        return await self._upsert_returning_id(
            GitHubReleaseModel,
            {
                "repository_id": repository_id,
                "github_release_id": release.github_id,
                "author_id": author_id,
                "tag_name": release.tag_name,
                "target_commitish": release.target_commitish,
                "name": release.name,
                "body": release.body,
                "draft": release.draft,
                "prerelease": release.prerelease,
                "html_url": release.html_url,
                "created_at": release.created_at,
                "published_at": release.published_at,
            },
            ["repository_id", "github_release_id"],
            [
                "author_id",
                "tag_name",
                "target_commitish",
                "name",
                "body",
                "draft",
                "prerelease",
                "html_url",
                "published_at",
            ],
        )

    async def _upsert_returning_id(
        self,
        model: type[Any],
        values: dict[str, object],
        conflict_columns: list[str],
        update_columns: list[str],
    ) -> UUID:
        statement = insert(model).values(**values)
        result = await self.session.execute(
            statement.on_conflict_do_update(
                index_elements=[getattr(model, column) for column in conflict_columns],
                set_={column: getattr(statement.excluded, column) for column in update_columns},
            ).returning(model.id)
        )
        return cast(UUID, result.scalar_one())

    @staticmethod
    def _changed_file_values(changed_file: GitHubChangedFile) -> dict[str, object]:
        return {
            "filename": normalize_repository_path(changed_file.filename),
            "status": changed_file.status,
            "additions": changed_file.additions,
            "deletions": changed_file.deletions,
            "changes": changed_file.changes,
            "previous_filename": (
                normalize_repository_path(changed_file.previous_filename)
                if changed_file.previous_filename
                else None
            ),
            "blob_url": changed_file.blob_url,
        }
