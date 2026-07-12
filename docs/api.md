# Trace — API Specification

> HTTP API contract for the Trace Software Intelligence platform.

This document defines public backend endpoints, request/response schemas, validation rules, status codes, pagination, error handling, and examples.

Related documents:

- [`overview.md`](overview.md) — product context
- [`product.md`](product.md) — functional requirements
- [`architecture.md`](architecture.md) — system design
- [`ontology.md`](ontology.md) — entity and relationship model
- [`ai-system.md`](ai-system.md) — retrieval and reasoning
- [`database.md`](database.md) — persistence design

---

## 1. API Goals

The API must be:

- predictable
- typed
- resource-oriented
- idempotent where possible
- explicit about uncertainty
- explicit about partial data
- versionable
- easy to consume from the React frontend
- stable enough for evaluation tooling

---

## 2. Base URL

Local development:

```text
http://localhost:8000/api
```

Versioning strategy for MVP:

```text
/api
```

Future breaking version:

```text
/api/v2
```

---

## 3. Content Type

Requests:

```http
Content-Type: application/json
```

Responses:

```http
Content-Type: application/json
```

UTF-8 required.

---

## 4. Authentication

MVP:

```text
No user authentication.
```

GitHub access uses a server-side read-only token.

The token is never exposed to clients.

Future:

- Google OAuth
- private repositories
- user workspaces
- organization access

---

## 5. Common Headers

Recommended request headers:

```http
Accept: application/json
X-Request-ID: optional-client-generated-id
```

Response headers:

```http
X-Request-ID: server-request-id
```

Potential rate-limit headers later:

```http
X-RateLimit-Limit
X-RateLimit-Remaining
X-RateLimit-Reset
```

---

## 6. Common Response Conventions

## 6.1 Success Envelope

Resource endpoints return direct typed payloads.

Example:

```json
{
  "id": "repo_uuid",
  "owner": "tiangolo",
  "name": "fastapi"
}
```

List endpoints return:

```json
{
  "items": [],
  "page": 1,
  "page_size": 20,
  "total": 0,
  "has_next": false
}
```

## 6.2 Error Envelope

```json
{
  "error": {
    "code": "repository_not_found",
    "message": "The requested repository does not exist.",
    "retryable": false,
    "details": {},
    "request_id": "req_123"
  }
}
```

Required fields:

- `code`
- `message`
- `retryable`
- `request_id`

Optional:

- `details`

---

## 7. Standard Error Codes

```text
validation_error
repository_not_found
repository_private
repository_unsupported
repository_too_large
repository_already_indexed
ingestion_not_found
ingestion_conflict
atlas_not_ready
atlas_partial
entity_not_found
evidence_not_found
rate_limited
provider_unavailable
github_unavailable
embedding_unavailable
llm_unavailable
database_error
internal_error
```

---

## 8. Standard HTTP Status Codes

| Status | Meaning |
|---|---|
| 200 | Successful read |
| 201 | Resource created |
| 202 | Accepted for async processing |
| 204 | Successful operation with no body |
| 400 | Invalid request |
| 404 | Resource not found |
| 409 | Conflicting state |
| 422 | Validation failed |
| 429 | Rate limited |
| 500 | Internal failure |
| 502 | External provider failed |
| 503 | Service temporarily unavailable |

---

## 9. IDs

Internal IDs are UUID strings.

Example:

```text
550e8400-e29b-41d4-a716-446655440000
```

GitHub-specific IDs are exposed separately.

Never use repository name alone as internal identity.

---

## 10. Timestamps

All timestamps use ISO 8601 UTC.

Example:

```text
2026-07-12T20:00:00Z
```

---

## 11. Pagination

Query parameters:

```text
page
page_size
```

Defaults:

```text
page=1
page_size=20
```

Limits:

```text
1 <= page_size <= 100
```

Response:

```json
{
  "items": [],
  "page": 1,
  "page_size": 20,
  "total": 145,
  "has_next": true
}
```

Cursor pagination may replace page pagination later for large artifact collections.

---

## 12. Sorting

Common parameters:

```text
sort
order
```

Example:

```text
?sort=created_at&order=desc
```

Allowed order:

```text
asc
desc
```

Unsupported sort fields return `422`.

---

## 13. Filtering

Filters are endpoint-specific.

Common filters:

```text
status
type
confidence
date_from
date_to
subsystem_id
contributor_id
```

Unknown filters should return `422` in strict endpoints.

---

# 14. Health Endpoints

## 14.1 Liveness

```http
GET /health/live
```

Response:

```json
{
  "status": "ok"
}
```

Status:

```text
200
```

## 14.2 Readiness

```http
GET /health/ready
```

Checks:

- database
- Redis
- migrations
- required config

Response:

```json
{
  "status": "ready",
  "checks": {
    "database": "ok",
    "redis": "ok"
  }
}
```

Possible status:

```text
200
503
```

---

# 15. Repository Endpoints

## 15.1 Create or Reuse Repository

```http
POST /repositories
```

Purpose:

- validate public GitHub URL
- create repository record
- create ingestion job
- reuse existing ready Atlas when applicable

Request:

```json
{
  "url": "https://github.com/tiangolo/fastapi"
}
```

Validation:

- valid HTTPS GitHub URL
- repository root URL only
- owner required
- repository required
- public repository
- supported size limits

Success — new ingestion:

```http
202 Accepted
```

```json
{
  "repository": {
    "id": "repo_uuid",
    "github_id": 160919119,
    "owner": "tiangolo",
    "name": "fastapi",
    "full_name": "tiangolo/fastapi",
    "default_branch": "master",
    "description": "FastAPI framework...",
    "primary_language": "Python",
    "status": "queued",
    "atlas_url": "/repositories/repo_uuid/overview"
  },
  "ingestion_job": {
    "id": "job_uuid",
    "status": "queued",
    "stage": "pending",
    "progress": 0
  },
  "reused_existing_atlas": false
}
```

Success — existing Atlas:

```http
200 OK
```

```json
{
  "repository": {
    "id": "repo_uuid",
    "owner": "tiangolo",
    "name": "fastapi",
    "status": "ready",
    "atlas_url": "/repositories/repo_uuid/overview"
  },
  "ingestion_job": null,
  "reused_existing_atlas": true
}
```

Errors:

```text
422 validation_error
404 repository_not_found
403 repository_private
422 repository_unsupported
422 repository_too_large
429 rate_limited
502 github_unavailable
```

---

## 15.2 List Repositories

```http
GET /repositories
```

Query parameters:

```text
page
page_size
status
owner
search
sort
order
```

Response:

```json
{
  "items": [
    {
      "id": "repo_uuid",
      "owner": "tiangolo",
      "name": "fastapi",
      "full_name": "tiangolo/fastapi",
      "primary_language": "Python",
      "status": "ready",
      "last_indexed_at": "2026-07-12T20:00:00Z"
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 1,
  "has_next": false
}
```

---

## 15.3 Get Repository

```http
GET /repositories/{repository_id}
```

Response:

```json
{
  "id": "repo_uuid",
  "github_id": 160919119,
  "owner": "tiangolo",
  "name": "fastapi",
  "full_name": "tiangolo/fastapi",
  "description": "FastAPI framework...",
  "default_branch": "master",
  "primary_language": "Python",
  "visibility": "public",
  "is_archived": false,
  "is_fork": false,
  "status": "ready",
  "analysis_mode": "full",
  "analysis_limitations": [],
  "source_url": "https://github.com/tiangolo/fastapi",
  "head_commit_sha": "abc123",
  "created_at": "2026-07-12T19:00:00Z",
  "updated_at": "2026-07-12T20:00:00Z",
  "last_indexed_at": "2026-07-12T20:00:00Z"
}
```

Errors:

```text
404 repository_not_found
```

---

## 15.4 Reindex Repository

```http
POST /repositories/{repository_id}/reindex
```

Purpose:

Create a new snapshot when default branch HEAD changed.

Request:

```json
{
  "force": false
}
```

Response:

```http
202 Accepted
```

```json
{
  "job_id": "job_uuid",
  "repository_id": "repo_uuid",
  "status": "queued"
}
```

Conflicts:

```text
409 ingestion_conflict
```

MVP may omit this endpoint until incremental/reindex support exists.

---

# 16. Ingestion Endpoints

## 16.1 Get Latest Ingestion

```http
GET /repositories/{repository_id}/ingestion
```

Response:

```json
{
  "id": "job_uuid",
  "repository_id": "repo_uuid",
  "status": "running",
  "stage": "build_graph",
  "progress": 63,
  "started_at": "2026-07-12T19:30:00Z",
  "completed_at": null,
  "error": null,
  "stages": [
    {
      "name": "validate",
      "status": "completed",
      "progress": 100,
      "attempts": 1,
      "started_at": "2026-07-12T19:30:00Z",
      "completed_at": "2026-07-12T19:30:01Z",
      "error": null
    },
    {
      "name": "build_graph",
      "status": "running",
      "progress": 45,
      "attempts": 1,
      "started_at": "2026-07-12T19:35:00Z",
      "completed_at": null,
      "error": null
    }
  ]
}
```

Job status:

```text
pending
queued
running
completed
partial
failed
cancelled
```

Stage status:

```text
pending
running
completed
skipped
failed
```

---

## 16.2 Get Ingestion Job

```http
GET /ingestion-jobs/{job_id}
```

Same response model as latest ingestion endpoint.

---

## 16.3 Retry Failed Ingestion

```http
POST /ingestion-jobs/{job_id}/retry
```

Request:

```json
{
  "from_stage": "discover_subsystems"
}
```

Rules:

- only failed/partial jobs
- stage must be retryable
- completed deterministic stages remain preserved
- retry remains idempotent

Response:

```http
202 Accepted
```

```json
{
  "job_id": "new_job_uuid",
  "retry_of": "old_job_uuid",
  "status": "queued",
  "from_stage": "discover_subsystems"
}
```

Errors:

```text
404 ingestion_not_found
409 ingestion_conflict
422 validation_error
```

---

# 17. Overview Endpoint

```http
GET /repositories/{repository_id}/overview
```

Requirements:

- repository must be `ready` or `partial`
- partial response includes limitations

Response:

```json
{
  "repository": {
    "id": "repo_uuid",
    "owner": "tiangolo",
    "name": "fastapi",
    "description": "FastAPI framework...",
    "primary_language": "Python",
    "source_url": "https://github.com/tiangolo/fastapi"
  },
  "status": "ready",
  "analysis_mode": "full",
  "limitations": [],
  "summary": {
    "text": "FastAPI is a Python web framework...",
    "confidence": 0.94,
    "evidence_ids": ["evidence_uuid"]
  },
  "statistics": {
    "stars": 80000,
    "forks": 7000,
    "open_issues": 500,
    "contributors": 700,
    "releases": 200,
    "source_files": 1200,
    "artifacts": 5000
  },
  "languages": [
    {
      "name": "Python",
      "percentage": 93.4
    }
  ],
  "major_subsystems": [],
  "architecture_summary": {
    "text": "The repository is organized around...",
    "confidence": 0.87,
    "evidence_ids": []
  },
  "recent_releases": [],
  "important_decisions": [],
  "suggested_exploration": []
}
```

Errors:

```text
404 repository_not_found
409 atlas_not_ready
```

---

# 18. Architecture Endpoints

## 18.1 Get Architecture

```http
GET /repositories/{repository_id}/architecture
```

Query parameters:

```text
max_nodes
confidence_min
include_external
```

Response:

```json
{
  "summary": {
    "text": "The system is organized around...",
    "confidence": 0.86,
    "evidence_ids": []
  },
  "graph": {
    "nodes": [
      {
        "id": "node_uuid",
        "type": "Subsystem",
        "label": "Routing",
        "knowledge_kind": "inferred",
        "confidence": 0.88,
        "metadata": {}
      }
    ],
    "edges": [
      {
        "id": "edge_uuid",
        "source": "node_uuid",
        "target": "node_uuid_2",
        "type": "DEPENDS_ON",
        "knowledge_kind": "inferred",
        "confidence": 0.78,
        "evidence_ids": []
      }
    ]
  },
  "entry_points": [],
  "central_modules": [],
  "external_dependencies": [],
  "limitations": []
}
```

Validation:

```text
1 <= max_nodes <= 500
0.0 <= confidence_min <= 1.0
```

---

## 18.2 Get Architecture Node Detail

```http
GET /repositories/{repository_id}/architecture/nodes/{node_id}
```

Response:

```json
{
  "id": "node_uuid",
  "type": "Subsystem",
  "label": "Routing",
  "description": "Handles request routing...",
  "knowledge_kind": "inferred",
  "confidence": 0.88,
  "key_files": [],
  "dependencies": [],
  "depended_on_by": [],
  "metrics": {
    "pagerank": 0.07,
    "betweenness": 0.12
  },
  "related_decisions": [],
  "related_contributors": [],
  "evidence_ids": []
}
```

---

# 19. Subsystem Endpoints

## 19.1 List Subsystems

```http
GET /repositories/{repository_id}/subsystems
```

Query parameters:

```text
page
page_size
confidence_min
status
sort
order
```

Status:

```text
confirmed
candidate
```

Response item:

```json
{
  "id": "subsystem_uuid",
  "name": "Authentication",
  "slug": "authentication",
  "summary": "Handles user identity and token validation.",
  "confidence": 0.86,
  "status": "confirmed",
  "file_count": 34,
  "directory_count": 3,
  "decision_count": 5,
  "top_contributors": [],
  "last_activity_at": "2026-06-20T10:00:00Z"
}
```

---

## 19.2 Get Subsystem

```http
GET /repositories/{repository_id}/subsystems/{subsystem_id}
```

Response:

```json
{
  "id": "subsystem_uuid",
  "name": "Authentication",
  "summary": "Handles user identity and token validation.",
  "confidence": 0.86,
  "status": "confirmed",
  "discovery_signals": [
    {
      "type": "directory_boundary",
      "weight": 0.30
    },
    {
      "type": "import_community",
      "weight": 0.35
    }
  ],
  "directories": [],
  "key_files": [],
  "important_symbols": [],
  "internal_dependencies": [],
  "external_dependencies": [],
  "issues": [],
  "pull_requests": [],
  "decisions": [],
  "contributors": [],
  "timeline": [],
  "suggested_next_subsystems": [],
  "evidence_ids": []
}
```

---

# 20. Timeline Endpoint

```http
GET /repositories/{repository_id}/timeline
```

Query parameters:

```text
page
page_size
date_from
date_to
type
subsystem_id
contributor_id
release_id
sort
order
```

Event types:

```text
issue
pull_request
commit
release
decision
subsystem_milestone
```

Response:

```json
{
  "items": [
    {
      "id": "event_uuid",
      "type": "release",
      "title": "Release 1.0.0",
      "summary": "Introduced...",
      "occurred_at": "2026-01-01T00:00:00Z",
      "author": null,
      "confidence": null,
      "source_url": "https://github.com/...",
      "related_entities": [],
      "evidence_ids": []
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 1,
  "has_next": false,
  "charts": {
    "activity_by_month": [],
    "release_frequency": [],
    "contribution_trend": []
  }
}
```

---

# 21. Decision Endpoints

## 21.1 List Decisions

```http
GET /repositories/{repository_id}/decisions
```

Query parameters:

```text
page
page_size
status
confidence_min
subsystem_id
date_from
date_to
sort
order
```

Decision status:

```text
candidate
confirmed
insufficient_evidence
rejected
```

Normal UI should request:

```text
status=confirmed
```

Response item:

```json
{
  "id": "decision_uuid",
  "title": "Introduce dependency injection",
  "summary": "The project introduced...",
  "status": "confirmed",
  "confidence": 0.84,
  "decision_date": "2025-09-02T00:00:00Z",
  "evidence_count": 4,
  "affected_subsystems": [],
  "source_url": null
}
```

---

## 21.2 Get Decision

```http
GET /repositories/{repository_id}/decisions/{decision_id}
```

Response:

```json
{
  "id": "decision_uuid",
  "title": "Introduce dependency injection",
  "context": "The codebase had...",
  "decision": "Adopt dependency injection...",
  "alternatives": [
    {
      "text": "Continue direct construction",
      "supported": true,
      "evidence_ids": []
    }
  ],
  "outcome": "Services became...",
  "status": "confirmed",
  "confidence": 0.84,
  "decision_date": "2025-09-02T00:00:00Z",
  "related_issue": {},
  "related_discussion": null,
  "implementing_pull_request": {},
  "commits": [],
  "affected_files": [],
  "affected_subsystems": [],
  "evidence_chain": [],
  "evidence_ids": []
}
```

Rules:

- confirmed decision requires evidence
- alternatives omitted when unsupported
- summary and direct evidence remain distinct

---

# 22. Contributor Endpoints

## 22.1 List Contributors

```http
GET /repositories/{repository_id}/contributors
```

Query parameters:

```text
page
page_size
subsystem_id
include_bots
sort
order
```

Sort fields:

```text
activity
recency
expertise_score
pull_requests
commits
```

Response item:

```json
{
  "id": "person_uuid",
  "login": "octocat",
  "display_name": "The Octocat",
  "avatar_url": "https://...",
  "profile_url": "https://github.com/octocat",
  "is_bot": false,
  "total_activity": 120,
  "active_subsystems": [],
  "recency_score": 0.92,
  "expertise_score": 0.81,
  "expertise_label": "strong repository activity"
}
```

---

## 22.2 Get Contributor

```http
GET /repositories/{repository_id}/contributors/{contributor_id}
```

Response:

```json
{
  "id": "person_uuid",
  "login": "octocat",
  "display_name": "The Octocat",
  "avatar_url": "https://...",
  "profile_url": "https://github.com/octocat",
  "is_bot": false,
  "summary": "Repository evidence suggests strong activity in...",
  "authored_pull_requests": [],
  "reviewed_pull_requests": [],
  "commits": [],
  "modified_files": [],
  "active_subsystems": [],
  "activity_timeline": [],
  "recent_work": [],
  "expertise_score": {
    "total": 0.81,
    "components": {
      "authored_prs": 0.25,
      "reviewed_prs": 0.20,
      "commits": 0.15,
      "subsystem_files": 0.12,
      "recency": 0.09
    }
  }
}
```

---

# 23. Graph Endpoints

## 23.1 Get Initial Graph

```http
GET /repositories/{repository_id}/graph
```

Query parameters:

```text
view
node_types
edge_types
confidence_min
limit
```

Views:

```text
architecture
repository
subsystem
decision
```

Validation:

```text
1 <= limit <= 500
```

Response:

```json
{
  "nodes": [],
  "edges": [],
  "truncated": false,
  "available_node_types": [],
  "available_edge_types": []
}
```

---

## 23.2 Expand Graph Node

```http
GET /repositories/{repository_id}/graph/nodes/{node_id}/neighbors
```

Query parameters:

```text
depth
node_types
edge_types
confidence_min
limit
```

Validation:

```text
1 <= depth <= 3
1 <= limit <= 500
```

Response:

```json
{
  "root_node_id": "node_uuid",
  "nodes": [],
  "edges": [],
  "truncated": false
}
```

---

## 23.3 Get Graph Path

```http
GET /repositories/{repository_id}/graph/path
```

Query parameters:

```text
source_id
target_id
max_depth
```

Response:

```json
{
  "found": true,
  "path": [
    {
      "node": {},
      "edge_to_next": {}
    }
  ]
}
```

---

# 24. Search Endpoint

```http
GET /repositories/{repository_id}/search
```

Query parameters:

```text
q
types
mode
page
page_size
```

Modes:

```text
exact
prefix
semantic
hybrid
```

Example:

```http
GET /repositories/repo_uuid/search?q=authentication&types=File,Subsystem&mode=hybrid
```

Response:

```json
{
  "query": "authentication",
  "mode": "hybrid",
  "items": [
    {
      "id": "entity_uuid",
      "type": "File",
      "title": "auth_service.py",
      "snippet": "Authentication service...",
      "score": 0.92,
      "knowledge_kind": "deterministic",
      "confidence": null,
      "source_url": "https://github.com/..."
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 1,
  "has_next": false
}
```

Rules:

- exact matches rank above weaker semantic matches
- inferred results expose confidence
- empty query rejected

---

# 25. Ask Endpoint

```http
POST /repositories/{repository_id}/query
```

Request:

```json
{
  "question": "Why was Redis introduced?",
  "conversation_id": null,
  "filters": {
    "subsystem_ids": [],
    "date_from": null,
    "date_to": null
  }
}
```

Validation:

```text
1 <= question length <= 2000
```

Response:

```json
{
  "id": "query_uuid",
  "question": "Why was Redis introduced?",
  "answer": "Redis appears to have been introduced...",
  "confidence": 0.73,
  "confidence_label": "medium",
  "intent": "decision",
  "retrieval_strategy": "adaptive_hybrid",
  "evidence": [
    {
      "id": "evidence_uuid",
      "source_type": "PullRequest",
      "source_title": "Add background job retries",
      "source_url": "https://github.com/...",
      "excerpt": "Use Redis to coordinate...",
      "relationship": "supports",
      "confidence": 0.91
    }
  ],
  "citations": [
    {
      "index": 1,
      "evidence_id": "evidence_uuid"
    }
  ],
  "graph_path": [],
  "related_files": [],
  "related_decisions": [],
  "timeline_events": [],
  "limitations": [
    "No explicit architecture decision record was found."
  ],
  "possible_interpretations": [
    {
      "text": "Redis may have been introduced for retry coordination.",
      "label": "inference",
      "confidence": 0.62
    }
  ],
  "suggested_follow_up": [
    "Show the pull requests that introduced Redis."
  ],
  "latency_ms": 4280
}
```

Required behavior:

- answer cites evidence when available
- unsupported certainty prohibited
- insufficient evidence returns related evidence
- possible interpretation clearly labeled
- retrieval strategy exposed for evaluation/debug mode

Errors:

```text
409 atlas_not_ready
503 llm_unavailable
503 embedding_unavailable
```

---

# 26. Evidence Endpoint

```http
GET /evidence/{evidence_id}
```

Response:

```json
{
  "id": "evidence_uuid",
  "repository_id": "repo_uuid",
  "snapshot_id": "snapshot_uuid",
  "source_entity": {
    "id": "entity_uuid",
    "type": "PullRequest",
    "title": "Add Redis-backed retries"
  },
  "target_entity": {
    "id": "decision_uuid",
    "type": "Decision",
    "title": "Introduce Redis"
  },
  "evidence_type": "artifact",
  "relationship": "supports",
  "content": "Use Redis to coordinate retry state.",
  "source_url": "https://github.com/...",
  "start_line": null,
  "end_line": null,
  "knowledge_kind": "deterministic",
  "confidence": 0.91,
  "provenance": {
    "provider": "github",
    "extraction_method": "decision_extractor",
    "extractor_version": "1.0.0",
    "model_name": "provider-model",
    "prompt_version": "decision-v3"
  },
  "created_at": "2026-07-12T20:00:00Z"
}
```

Errors:

```text
404 evidence_not_found
```

---

# 27. Entity Endpoint

Optional generic endpoint:

```http
GET /repositories/{repository_id}/entities/{entity_id}
```

Response:

```json
{
  "id": "entity_uuid",
  "type": "File",
  "canonical_key": "repo:...:file:backend/auth.py",
  "name": "auth.py",
  "description": null,
  "knowledge_kind": "deterministic",
  "confidence": null,
  "metadata": {},
  "evidence_ids": [],
  "source_url": "https://github.com/..."
}
```

Useful for graph detail panels.

---

# 28. Atlas Status Endpoint

```http
GET /repositories/{repository_id}/atlas/status
```

Response:

```json
{
  "repository_id": "repo_uuid",
  "status": "partial",
  "available_sections": [
    "overview",
    "architecture",
    "timeline",
    "contributors",
    "explore"
  ],
  "unavailable_sections": [
    {
      "section": "decisions",
      "reason": "llm_provider_failed",
      "retryable": true
    }
  ],
  "limitations": [
    "Decision extraction unavailable."
  ]
}
```

---

# 29. Common Schemas

## 29.1 Confidence

```json
{
  "value": 0.84,
  "label": "high"
}
```

Bands:

```text
high >= 0.80
medium >= 0.55 and < 0.80
low < 0.55
```

## 29.2 Entity Summary

```json
{
  "id": "entity_uuid",
  "type": "File",
  "title": "auth.py",
  "description": null,
  "knowledge_kind": "deterministic",
  "confidence": null,
  "source_url": "https://github.com/..."
}
```

## 29.3 Evidence Summary

```json
{
  "id": "evidence_uuid",
  "source_type": "PullRequest",
  "source_title": "Add Redis",
  "source_url": "https://github.com/...",
  "excerpt": "Use Redis...",
  "relationship": "supports",
  "confidence": 0.91
}
```

## 29.4 Graph Node

```json
{
  "id": "node_uuid",
  "type": "Subsystem",
  "label": "Authentication",
  "knowledge_kind": "inferred",
  "confidence": 0.86,
  "metadata": {}
}
```

## 29.5 Graph Edge

```json
{
  "id": "edge_uuid",
  "source": "source_uuid",
  "target": "target_uuid",
  "type": "PART_OF_SUBSYSTEM",
  "knowledge_kind": "inferred",
  "confidence": 0.82,
  "evidence_ids": []
}
```

---

# 30. Validation Rules

## 30.1 Repository URL

Must:

- use HTTPS
- use `github.com`
- identify owner
- identify repository
- not identify nested artifact

## 30.2 Confidence

```text
0.0 <= confidence <= 1.0
```

## 30.3 Date Range

`date_from` must not exceed `date_to`.

## 30.4 Graph Depth

```text
1 <= depth <= 3
```

## 30.5 Question Length

```text
1 <= length <= 2000
```

## 30.6 Page Size

```text
1 <= page_size <= 100
```

---

# 31. Partial Data Semantics

Ready response:

```json
{
  "status": "ready",
  "limitations": []
}
```

Partial response:

```json
{
  "status": "partial",
  "limitations": [
    "Decision extraction failed.",
    "TypeScript parser unavailable for 12 files."
  ]
}
```

Partial data should return `200` when the requested section is usable.

Use `409 atlas_not_ready` only when section is unavailable.

---

# 32. Idempotency

## 32.1 Repository Creation

Submitting same normalized repository URL should:

- return existing ready Atlas
- return active ingestion job
- avoid duplicate records

## 32.2 Retry

Retry creates a new job linked to prior job.

Completed stage outputs remain reused when valid.

## 32.3 Optional Idempotency Key

Future header:

```http
Idempotency-Key: client-generated-key
```

Useful for expensive POST endpoints.

---

# 33. Rate Limiting

MVP may implement basic limits on:

- repository creation
- Ask endpoint
- reindex
- retry

Potential response:

```http
429 Too Many Requests
```

```json
{
  "error": {
    "code": "rate_limited",
    "message": "Too many requests.",
    "retryable": true,
    "details": {
      "retry_after_seconds": 60
    },
    "request_id": "req_123"
  }
}
```

---

# 34. Caching

Read endpoints may return:

```http
ETag
Cache-Control
```

Atlas section cache key includes:

- repository ID
- snapshot ID
- Atlas generator version
- query parameters

Ask responses are not publicly cacheable by default.

---

# 35. CORS

Local development:

```text
http://localhost:5173
```

Production origins configured through environment variables.

Wildcard origins prohibited in production.

---

# 36. OpenAPI

FastAPI generates OpenAPI docs.

Development URLs:

```text
/docs
/redoc
/openapi.json
```

Requirements:

- every route tagged
- every request typed
- every response typed
- documented error responses
- examples included
- internal fields excluded

---

# 37. API Tags

Recommended tags:

```text
Health
Repositories
Ingestion
Overview
Architecture
Subsystems
Timeline
Decisions
Contributors
Graph
Search
Ask
Evidence
```

---

# 38. Frontend Query Keys

Suggested TanStack Query keys:

```ts
["repository", repositoryId]
["ingestion", repositoryId]
["overview", repositoryId]
["architecture", repositoryId, filters]
["subsystems", repositoryId, filters]
["subsystem", repositoryId, subsystemId]
["timeline", repositoryId, filters]
["decisions", repositoryId, filters]
["decision", repositoryId, decisionId]
["contributors", repositoryId, filters]
["contributor", repositoryId, contributorId]
["graph", repositoryId, filters]
["search", repositoryId, query, filters]
["evidence", evidenceId]
```

---

# 39. API Testing Requirements

## 39.1 Unit

Test:

- schema validation
- URL normalization
- error mapping
- confidence validation
- enum validation

## 39.2 Integration

Test:

- database reads/writes
- pagination
- filtering
- graph retrieval
- vector search
- retry behavior

## 39.3 Contract

Test:

- response shape
- status codes
- error payloads
- OpenAPI compatibility
- frontend generated types later

## 39.4 End-to-End

Test:

- create repository
- poll ingestion
- open Overview
- inspect subsystem
- inspect decision
- Ask question
- inspect evidence

---

# 40. Endpoint Priority

## P0

```text
POST /repositories
GET /repositories/{id}
GET /repositories/{id}/ingestion
GET /repositories/{id}/overview
GET /evidence/{id}
GET /health/live
GET /health/ready
```

## P1

```text
GET /repositories/{id}/architecture
GET /repositories/{id}/subsystems
GET /repositories/{id}/subsystems/{subsystem_id}
GET /repositories/{id}/timeline
GET /repositories/{id}/decisions
GET /repositories/{id}/decisions/{decision_id}
GET /repositories/{id}/contributors
GET /repositories/{id}/contributors/{contributor_id}
GET /repositories/{id}/graph
GET /repositories/{id}/graph/nodes/{node_id}/neighbors
GET /repositories/{id}/search
POST /repositories/{id}/query
```

## P2

```text
POST /repositories/{id}/reindex
POST /ingestion-jobs/{job_id}/retry
GET /repositories/{id}/graph/path
GET /repositories/{id}/atlas/status
GET /repositories/{id}/entities/{entity_id}
```

---

# 41. Example Full Flow

## Step 1

```http
POST /api/repositories
```

```json
{
  "url": "https://github.com/tiangolo/fastapi"
}
```

## Step 2

```http
GET /api/repositories/{repository_id}/ingestion
```

Poll until:

```json
{
  "status": "completed",
  "progress": 100
}
```

## Step 3

```http
GET /api/repositories/{repository_id}/overview
```

## Step 4

```http
GET /api/repositories/{repository_id}/architecture
```

## Step 5

```http
POST /api/repositories/{repository_id}/query
```

```json
{
  "question": "How does dependency injection work?"
}
```

## Step 6

Open returned evidence:

```http
GET /api/evidence/{evidence_id}
```

---

# 42. Non-Goals

MVP API does not include:

- user accounts
- auth tokens
- billing
- private repository credentials
- organization administration
- team permissions
- webhook ingestion
- mutation of GitHub repositories
- code generation
- code editing
- real-time collaboration

---

# 43. Definition of API Success

The API succeeds when:

- frontend can build every MVP surface without undocumented data
- long-running ingestion never blocks HTTP requests
- progress is observable
- partial data is explicit
- errors are stable and actionable
- inference exposes confidence
- evidence is navigable
- retries are idempotent
- contracts remain typed and testable

---

## Final API Rule

> Every API response that contains inferred knowledge must expose enough confidence and evidence metadata for the client to present uncertainty honestly.
