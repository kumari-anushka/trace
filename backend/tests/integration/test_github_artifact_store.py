import json
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from uuid import uuid4
from zipfile import ZipFile

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import async_session_factory
from src.github.classification import extract_text_files_from_zip
from src.github.models import (
    GitHubCommit as GitHubCommitModel,
)
from src.github.models import (
    GitHubIssue as GitHubIssueModel,
)
from src.github.models import (
    GitHubPerson,
    SourceFile,
    SourceFileContent,
)
from src.github.models import (
    GitHubPullRequest as GitHubPullRequestModel,
)
from src.github.models import (
    GitHubPullRequestReview as GitHubPullRequestReviewModel,
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
    GitHubPullRequest,
    GitHubRelease,
    GitHubReview,
    GitHubTree,
)
from src.github.store import GitHubArtifactStore
from src.repositories.store import RepositoryStore
from src.repository_versions.store import RepositoryVersionStore

FIXTURES = Path(__file__).parents[1] / "fixtures" / "github"
SNAPSHOT_SHA = "a" * 40


async def row_count(
    session: AsyncSession,
    model: type[object],
    condition: object,
) -> int:
    result = await session.execute(
        select(func.count()).select_from(model).where(condition)  # type: ignore[arg-type]
    )
    return result.scalar_one()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_github_artifacts_are_idempotent_and_keep_git_identity_separate() -> None:
    now = datetime.now(UTC)
    suffix = uuid4().hex
    actor = {
        "id": 9001,
        "login": "octocat",
        "html_url": "https://github.com/octocat",
        "type": "User",
    }
    label = GitHubLabel.model_validate({"id": 7001, "name": "ingestion", "color": "1d76db"})
    issue = GitHubIssue.model_validate(
        {
            "id": 5001,
            "number": 12,
            "user": actor,
            "title": "Fixed snapshots",
            "state": "open",
            "html_url": "https://github.test/issues/12",
            "labels": [label.model_dump(by_alias=True)],
            "created_at": now,
            "updated_at": now,
        }
    )
    pull_request = GitHubPullRequest.model_validate(
        {
            "id": 5002,
            "number": 13,
            "user": actor,
            "title": "Add snapshots",
            "state": "closed",
            "html_url": "https://github.test/pull/13",
            "head": {"sha": "b" * 40},
            "base": {"sha": "c" * 40},
            "labels": [label.model_dump(by_alias=True)],
            "created_at": now,
            "updated_at": now,
            "merged_at": now,
        }
    )
    changed_file = GitHubChangedFile(
        filename="src/main.py",
        status="modified",
        additions=4,
        deletions=1,
        changes=5,
    )
    review = GitHubReview.model_validate(
        {
            "id": 6001,
            "user": actor,
            "state": "APPROVED",
            "commit_id": "b" * 40,
            "submitted_at": now,
        }
    )
    commit = GitHubCommit.model_validate(
        {
            "sha": SNAPSHOT_SHA,
            "html_url": "https://github.test/commit/snapshot",
            "author": actor,
            "committer": actor,
            "commit": {
                "message": "Add snapshot ingestion",
                "author": {
                    "name": "A Git Author",
                    "email": "git-author@example.test",
                    "date": now.isoformat(),
                },
                "committer": {
                    "name": "A Git Committer",
                    "email": "git-committer@example.test",
                    "date": now.isoformat(),
                },
            },
            "parents": [{"sha": "d" * 40}],
            "files": [changed_file.model_dump()],
        }
    )
    release = GitHubRelease.model_validate(
        {
            "id": 8001,
            "author": actor,
            "tag_name": "v0.1.0",
            "target_commitish": "main",
            "html_url": "https://github.test/releases/v0.1.0",
            "created_at": now,
            "published_at": now,
        }
    )
    contributor = GitHubContributor.model_validate({**actor, "contributions": 10})
    tree = GitHubTree.model_validate(json.loads((FIXTURES / "source_tree.json").read_text()))
    archive_buffer = BytesIO()
    with ZipFile(archive_buffer, "w") as archive:
        archive.writestr("acme-trace/src/main.py", "print('trace')\n")
        archive.writestr("acme-trace/tests/test_main.py", "def test_main(): pass\n")
        archive.writestr("acme-trace/README.md", "# Trace\n")
    extraction = extract_text_files_from_zip(
        archive_buffer.getvalue(),
        allowed_paths={"src/main.py", "tests/test_main.py", "README.md"},
        max_file_bytes=1_000,
    )

    async with async_session_factory() as session:
        repository_store = RepositoryStore(session=session)
        repository = await repository_store.create(
            github_id=uuid4().int % (2**63 - 1),
            github_url=f"https://github.com/acme/trace-{suffix}",
            owner="acme",
            name=f"trace-{suffix}",
            default_branch="main",
        )
        version = await RepositoryVersionStore(session=session).create(
            repository_id=repository.id,
            commit_sha=SNAPSHOT_SHA,
            branch="main",
        )
        await session.commit()

        try:
            store = GitHubArtifactStore(session=session)
            for _ in range(2):
                await store.replace_source_tree(
                    repository_version_id=version.id,
                    tree=tree,
                )
                await store.replace_source_contents(
                    repository_version_id=version.id,
                    extraction=extraction,
                )
                await store.persist_artifacts(
                    repository_id=repository.id,
                    repository_version_id=version.id,
                    labels=[label],
                    issues=[issue],
                    pull_requests=[pull_request],
                    pull_request_files={13: [changed_file]},
                    pull_request_reviews={13: [review]},
                    commits=[commit],
                    releases=[release],
                    contributors=[contributor],
                    bounds={"snapshot_sha": SNAPSHOT_SHA, "commits": 100},
                )
                await session.commit()

            assert (
                await row_count(
                    session,
                    SourceFile,
                    SourceFile.repository_version_id == version.id,
                )
                == 4
            )
            content_count = (
                await session.execute(
                    select(func.count())
                    .select_from(SourceFileContent)
                    .join(SourceFile, SourceFileContent.source_file_id == SourceFile.id)
                    .where(SourceFile.repository_version_id == version.id)
                )
            ).scalar_one()
            assert content_count == 3
            for model in (
                GitHubPerson,
                GitHubIssueModel,
                GitHubPullRequestModel,
                GitHubPullRequestReviewModel,
                GitHubCommitModel,
                GitHubReleaseModel,
            ):
                assert (
                    await row_count(
                        session,
                        model,
                        model.repository_id == repository.id,
                    )
                    == 1
                )

            persisted_commit = (
                await session.execute(
                    select(GitHubCommitModel).where(
                        GitHubCommitModel.repository_id == repository.id
                    )
                )
            ).scalar_one()
            assert persisted_commit.git_author_email == "git-author@example.test"
            assert persisted_commit.author_id is not None
        finally:
            await repository_store.delete(repository)
            await session.commit()
