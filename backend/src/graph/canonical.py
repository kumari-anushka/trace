from hashlib import sha256
from uuid import UUID


def snapshot_key(repository_id: UUID, repository_version_id: UUID) -> str:
    return f"repo:{repository_id}:snapshot:{repository_version_id}"


def directory_key(repository_id: UUID, repository_version_id: UUID, path: str) -> str:
    return f"{snapshot_key(repository_id, repository_version_id)}:directory:{path}"


def file_key(repository_id: UUID, repository_version_id: UUID, path: str) -> str:
    return f"{snapshot_key(repository_id, repository_version_id)}:file:{path}"


def symbol_key(
    repository_id: UUID,
    repository_version_id: UUID,
    path: str,
    qualified_name: str,
) -> str:
    return f"{snapshot_key(repository_id, repository_version_id)}:symbol:{path}:{qualified_name}"


def external_dependency_key(
    repository_id: UUID,
    repository_version_id: UUID,
    ecosystem: str,
    name: str,
) -> str:
    return (
        f"{snapshot_key(repository_id, repository_version_id)}:"
        f"external_dependency:{ecosystem}:{name}"
    )


def subsystem_key(
    repository_id: UUID,
    repository_version_id: UUID,
    member_canonical_keys: tuple[str, ...],
) -> str:
    digest = sha256("\0".join(member_canonical_keys).encode()).hexdigest()
    return f"{snapshot_key(repository_id, repository_version_id)}:subsystem:{digest}"


def architecture_summary_key(repository_id: UUID, repository_version_id: UUID) -> str:
    return f"{snapshot_key(repository_id, repository_version_id)}:architecture_summary"


def decision_key(
    repository_id: UUID,
    repository_version_id: UUID,
    source_canonical_key: str,
) -> str:
    digest = sha256(source_canonical_key.encode()).hexdigest()
    return f"{snapshot_key(repository_id, repository_version_id)}:decision:{digest}"


def person_key(github_user_id: int) -> str:
    return f"github:person:{github_user_id}"


def issue_key(repository_id: UUID, number: int) -> str:
    return f"github:issue:{repository_id}:{number}"


def pull_request_key(repository_id: UUID, number: int) -> str:
    return f"github:pull_request:{repository_id}:{number}"


def commit_key(repository_id: UUID, sha: str) -> str:
    return f"github:commit:{repository_id}:{sha}"


def release_key(repository_id: UUID, github_release_id: int) -> str:
    return f"github:release:{repository_id}:{github_release_id}"


def evidence_key(repository_id: UUID, repository_version_id: UUID, *parts: object) -> str:
    identity = ":".join(str(part) for part in parts)
    digest = sha256(identity.encode()).hexdigest()
    return f"{snapshot_key(repository_id, repository_version_id)}:evidence:{digest}"
