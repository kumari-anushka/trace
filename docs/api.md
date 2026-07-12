# Trace — API

Base URL:

```text
/api
```

## Conventions

- JSON only
- UUID internal IDs
- ISO 8601 UTC timestamps
- typed request/response models
- stable error codes
- pagination for lists

## Error Shape

```json
{
  "error": {
    "code": "repository_not_found",
    "message": "Repository does not exist.",
    "retryable": false,
    "details": {},
    "request_id": "req_123"
  }
}
```

## Pagination

```text
page=1
page_size=20
```

Max:

```text
100
```

Response:

```json
{
  "items": [],
  "page": 1,
  "page_size": 20,
  "total": 0,
  "has_next": false
}
```

## Health

```http
GET /health/live
GET /health/ready
```

## Repositories

### Create or Reuse

```http
POST /repositories
```

```json
{
  "url": "https://github.com/owner/repository"
}
```

Responses:

- `202` new ingestion
- `200` existing Atlas
- `422` invalid/unsupported
- `404` not found
- `403` private
- `429` rate limited

### List

```http
GET /repositories
```

### Detail

```http
GET /repositories/{repository_id}
```

### Reindex

```http
POST /repositories/{repository_id}/reindex
```

P2.

## Ingestion

```http
GET /repositories/{repository_id}/ingestion
GET /ingestion-jobs/{job_id}
POST /ingestion-jobs/{job_id}/retry
```

Job response includes:

- status
- stage
- progress
- timestamps
- error
- stage list

## Atlas

```http
GET /repositories/{id}/overview
GET /repositories/{id}/architecture
GET /repositories/{id}/subsystems
GET /repositories/{id}/subsystems/{subsystem_id}
GET /repositories/{id}/timeline
GET /repositories/{id}/decisions
GET /repositories/{id}/decisions/{decision_id}
GET /repositories/{id}/contributors
GET /repositories/{id}/contributors/{contributor_id}
GET /repositories/{id}/atlas/status
```

Every inferred object exposes:

- confidence
- evidence IDs
- knowledge kind
- limitations where relevant

## Graph

```http
GET /repositories/{id}/graph
GET /repositories/{id}/graph/nodes/{node_id}/neighbors
GET /repositories/{id}/graph/path
```

Limits:

```text
depth <= 3
nodes <= 500
```

## Search

```http
GET /repositories/{id}/search
```

Parameters:

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

## Ask

```http
POST /repositories/{id}/query
```

Request:

```json
{
  "question": "Why was Redis introduced?",
  "filters": {
    "subsystem_ids": [],
    "date_from": null,
    "date_to": null
  }
}
```

Response:

```json
{
  "answer": "Redis appears to have been introduced...",
  "confidence": 0.73,
  "intent": "decision",
  "retrieval_strategy": "adaptive_hybrid",
  "evidence": [],
  "citations": [],
  "graph_path": [],
  "related_files": [],
  "related_decisions": [],
  "timeline_events": [],
  "limitations": [],
  "possible_interpretations": [],
  "suggested_follow_up": []
}
```

Rules:

- question length 1–2000
- cited when evidence exists
- unsupported certainty prohibited
- weak evidence returns limitations + nearby evidence

## Evidence

```http
GET /evidence/{evidence_id}
```

Returns:

- source entity
- target entity/edge
- evidence type
- excerpt
- URL
- line range
- confidence
- provenance

## Status Codes

| Status | Meaning |
|---|---|
| 200 | Successful read |
| 201 | Created |
| 202 | Async work accepted |
| 400 | Bad request |
| 404 | Not found |
| 409 | Invalid state |
| 422 | Validation failed |
| 429 | Rate limited |
| 502 | Provider failure |
| 503 | Temporary unavailability |

## Common Error Codes

```text
validation_error
repository_not_found
repository_private
repository_unsupported
repository_too_large
ingestion_conflict
atlas_not_ready
entity_not_found
evidence_not_found
rate_limited
provider_unavailable
github_unavailable
embedding_unavailable
llm_unavailable
internal_error
```

## P0 Endpoints

```text
POST /repositories
GET /repositories/{id}
GET /repositories/{id}/ingestion
GET /repositories/{id}/overview
GET /evidence/{id}
GET /health/live
GET /health/ready
```

## P1 Endpoints

```text
architecture
subsystems
timeline
decisions
contributors
graph
search
query
```

## OpenAPI

FastAPI docs:

```text
/docs
/redoc
/openapi.json
```
