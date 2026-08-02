# Week 2 — GitHub Ingestion

Week 2 produces deterministic repository facts only. It does not generate AI
summaries or inferred architecture.

## Snapshot Semantics

Submission resolves and stores the default branch HEAD as
`repository_versions.commit_sha`. The worker never resolves that branch again.
It fetches the stored commit SHA, persists the commit's `source_tree_sha`, and
uses that tree SHA for the recursive source inventory.

Historical API calls are bounded and the commit listing is anchored with
`sha={repository_versions.commit_sha}`. The limits used for a run are stored in
`ingestion_artifact_snapshots`.

## Worker Stages

1. `fetch_repository_metadata`
   - repository metadata
   - snapshot verification
   - source-tree SHA
   - language distribution
2. `fetch_source_tree`
   - recursive source inventory
   - file classification
3. `fetch_source_contents`
   - fixed-SHA repository archive
   - normalized UTF-8 text
   - SHA-256 content hashes
4. `fetch_issues_and_labels`
5. `fetch_pull_requests`
   - per-PR changed files and reviews
   - durable per-PR checkpoints
6. `fetch_commits`
   - parents, changed files, and durable per-commit checkpoints
7. `fetch_releases_and_contributors`

Each completed stage persists an `output_summary` containing its snapshot
identity and artifact counts. The repository ingestion API and progress UI
expose these summaries.

## Idempotency

Provider identities are enforced with database constraints:

| Fact | Identity |
|---|---|
| Source file | repository version + normalized path |
| GitHub account | repository + GitHub user ID |
| Label | repository + GitHub label ID |
| Issue | repository + GitHub issue ID |
| Pull request | repository + GitHub pull-request ID |
| Review | repository + GitHub review ID |
| Commit | repository + SHA |
| Release | repository + GitHub release ID |

Persistence uses PostgreSQL conflict updates, while mutable join collections
such as labels and changed files are replaced within the stage transaction.
Reprocessing the same provider fixture therefore updates facts without adding
duplicates.

Commit Git identities (`name` and `email` from Git commit metadata) remain
separate from GitHub accounts. A commit may link to a GitHub account when the
provider supplies one, but matching is never inferred from an email address.

## File Classification

Every blob is assigned exactly one kind:

- `source`
- `test`
- `documentation`
- `binary`
- `generated`
- `ignored`

Repository paths are normalized as safe POSIX paths. Absolute paths and parent
traversal are rejected before persistence.

Text contents are stored separately in `source_file_contents`. Binary,
generated, and ignored inventory entries are excluded. Oversized,
NUL-containing, non-UTF-8, and missing candidate files are skipped with counts
in the stage summary. Line endings are normalized to LF before the content hash
is calculated.

## Pagination, Limits, and Retries

The provider adapter follows GitHub `Link` pagination and rejects pagination
URLs outside the configured GitHub API origin. History bounds are configurable:

```text
GITHUB_ISSUE_LIMIT=200
GITHUB_PULL_REQUEST_LIMIT=100
GITHUB_REVIEW_LIMIT_PER_PULL_REQUEST=100
GITHUB_CHANGED_FILE_LIMIT_PER_ARTIFACT=300
GITHUB_COMMIT_LIMIT=100
GITHUB_RELEASE_LIMIT=100
GITHUB_CONTRIBUTOR_LIMIT=100
GITHUB_LABEL_LIMIT=200
```

Transient network and provider failures use bounded exponential retries.
`Retry-After` and rate-limit reset headers are honored up to the configured
delay. An exhausted retryable failure is left pending in the Redis consumer
group and reclaimed by a worker; deterministic failures are persisted and
acknowledged.

Pull-request and commit stages persist a checkpoint after each artifact. A
retry skips completed provider IDs and SHAs instead of starting the stage over.
Stage and overall job percentages are committed with every checkpoint.

The worker also reconciles PostgreSQL `running` jobs with the Redis consumer
group at startup. A job whose mapped stream entry is no longer pending is
re-enqueued; an existing pending entry is left unchanged.

## Verification

Fixture tests cover pagination, rate-limit behavior, classification, fixed-SHA
routing, artifact persistence, and retry idempotency. Run:

```bash
cd backend
uv run pytest
uv run alembic check
```
