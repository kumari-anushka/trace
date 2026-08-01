# Trace API

This document describes the API that is implemented today. Planned Atlas
endpoints are listed separately and are not part of the current contract.

## Local URLs

```text
API base:    http://localhost:8000/api
Health:      http://localhost:8000/health
Swagger UI:  http://localhost:8000/docs
ReDoc:       http://localhost:8000/redoc
OpenAPI:     http://localhost:8000/openapi.json
```

`/health` is intentionally outside `/api` because it is used by Docker and
infrastructure monitoring. All product endpoints are under `/api`.

## Conventions

- Requests and responses use JSON.
- Internal identifiers are UUID strings.
- Timestamps are ISO 8601 values with timezone information.
- Repository snapshots are identified by immutable Git commit SHAs.
- PostgreSQL is the source of truth for ingestion progress.

## Error responses

Application errors use:

```json
{
  "message": "Repository not found"
}
```

Request-validation errors also include Pydantic's structured error list:

```json
{
  "message": "Invalid request",
  "errors": []
}
```

Currently used status codes:

| Status | Meaning |
|---|---|
| `200` | Successful read or delete |
| `201` | Repository, snapshot, and ingestion job created |
| `404` | Repository, snapshot, job, or GitHub resource not found |
| `409` | Existing repository, duplicate active job, or invalid state transition |
| `422` | Invalid URL, private repository, or request validation failure |
| `502` | GitHub provider failure |
| `503` | Ingestion job could not be dispatched |

## Health

### Check API health

```http
GET /health
```

Response:

```json
{
  "status": "ok"
}
```

## Repositories

### Import a public repository

```http
POST /api/repositories
Content-Type: application/json
```

Request:

```json
{
  "github_url": "https://github.com/owner/repository"
}
```

Successful response: `201 Created`

```json
{
  "repository": {
    "id": "9f5f4d06-8246-49bc-9937-8282ac03f69e",
    "github_id": 123456,
    "github_url": "https://github.com/owner/repository",
    "owner": "owner",
    "name": "repository",
    "default_branch": "main",
    "description": null,
    "homepage": null,
    "primary_language": null,
    "stars_count": 0,
    "forks_count": 0,
    "watchers_count": 0,
    "open_issues_count": 0,
    "archived": false,
    "disabled": false,
    "provider_created_at": null,
    "provider_updated_at": null,
    "provider_pushed_at": null,
    "created_at": "2026-08-01T12:00:00Z",
    "updated_at": "2026-08-01T12:00:00Z"
  },
  "repository_version": {
    "id": "42637082-b422-4f58-9582-3b47c5e04f3b",
    "repository_id": "9f5f4d06-8246-49bc-9937-8282ac03f69e",
    "commit_sha": "0123456789abcdef0123456789abcdef01234567",
    "branch": "main",
    "languages": null,
    "source_tree_sha": null,
    "source_tree_truncated": false,
    "created_at": "2026-08-01T12:00:00Z"
  },
  "ingestion_job": {
    "id": "4c734c20-6aa0-48f0-89fd-aad49609953b",
    "repository_version_id": "42637082-b422-4f58-9582-3b47c5e04f3b",
    "status": "queued",
    "progress": 0,
    "error_message": null,
    "created_at": "2026-08-01T12:00:00Z",
    "updated_at": "2026-08-01T12:00:00Z",
    "started_at": null,
    "completed_at": null
  }
}
```

Important errors:

- `404`: GitHub repository not found.
- `409`: Repository already exists.
- `422`: Invalid GitHub URL or private repository.
- `502`: GitHub API failure.
- `503`: Job could not be placed on the ingestion queue.

GitHub normally returns `404` when a private repository is not visible to the
configured token. Trace can return the specific private-repository error only
when GitHub exposes metadata containing `private: true`.

### List repositories

```http
GET /api/repositories
```

Response:

```json
{
  "repositories": []
}
```

### Get a repository

```http
GET /api/repositories/{repository_id}
```

### Delete a repository

```http
DELETE /api/repositories/{repository_id}
```

Deleting a repository cascades to its versions, ingestion jobs, and ingestion
stages.

Response:

```json
{
  "message": "Repository deleted successfully"
}
```

### Get repository ingestion progress

```http
GET /api/repositories/{repository_id}/ingestion
```

The newest ingestion job across the repository's snapshots is returned with
its ordered stages:

```json
{
  "repository_id": "9f5f4d06-8246-49bc-9937-8282ac03f69e",
  "ingestion_job": {
    "id": "4c734c20-6aa0-48f0-89fd-aad49609953b",
    "repository_version_id": "42637082-b422-4f58-9582-3b47c5e04f3b",
    "status": "running",
    "progress": 45,
    "error_message": null,
    "created_at": "2026-08-01T12:00:00Z",
    "updated_at": "2026-08-01T12:00:05Z",
    "started_at": "2026-08-01T12:00:01Z",
    "completed_at": null
  },
  "stages": [
    {
      "id": "ca00e29b-b70a-4a30-aaf5-234f41b6cdde",
      "ingestion_job_id": "4c734c20-6aa0-48f0-89fd-aad49609953b",
      "name": "fetch_source_tree",
      "position": 0,
      "status": "running",
      "progress": 45,
      "error_message": null,
      "output_summary": {
        "snapshot_sha": "0123456789abcdef0123456789abcdef01234567",
        "source_tree_sha": "89abcdef0123456789abcdef0123456789abcdef",
        "files": 412,
        "source": 218,
        "test": 96,
        "documentation": 31
      },
      "created_at": "2026-08-01T12:00:01Z",
      "updated_at": "2026-08-01T12:00:05Z",
      "started_at": "2026-08-01T12:00:01Z",
      "completed_at": null
    }
  ]
}
```

Job statuses:

```text
pending → queued → running → completed
                           ↘ failed
```

Stage statuses are `pending`, `running`, `completed`, `failed`, or `skipped`.
Completed Week 2 stages include count-based `output_summary` values. The
pipeline stages are `fetch_repository_metadata`, `fetch_source_tree`, and
`fetch_github_artifacts`.

## Repository versions

### List repository versions

```http
GET /api/repository-versions?repository_id={repository_id}
```

Versions are returned newest first.

### Get a repository version

```http
GET /api/repository-versions/{repository_version_id}
```

## Ingestion jobs

### Get an ingestion job

```http
GET /api/ingestion-jobs/{ingestion_job_id}
```

This lower-level endpoint returns the job itself. Use the repository ingestion
endpoint when the frontend also needs the ordered stage list.

## Idempotency

Trace permits at most one active ingestion job per immutable repository
version. Active means `pending`, `queued`, or `running`. Completed and failed
jobs remain as history and do not prevent a later retry.

The rule is enforced by both a service pre-check and a PostgreSQL partial
unique index, protecting against simultaneous requests.

## Planned endpoints

Atlas overview, architecture, subsystems, timeline, decisions, contributors,
graph, search, evidence, retry, and cited-question endpoints are planned for
later roadmap weeks. They are intentionally not documented as available yet.
