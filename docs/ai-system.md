# Trace — AI System

> Technical specification for repository intelligence, semantic enrichment, retrieval, reasoning, evidence verification, and AI evaluation.

This document defines how Trace converts repository artifacts into evidence-backed Software Atlas knowledge.

Related documents:

- [`overview.md`](overview.md) — product context
- [`product.md`](product.md) — functional requirements
- [`architecture.md`](architecture.md) — system structure
- [`ontology.md`](ontology.md) — entities, relationships, and evidence rules
- [`database.md`](database.md) — persistence design
- [`api.md`](api.md) — HTTP contracts
- [`evaluation.md`](evaluation.md) — experiments and quality metrics

---

## 1. Purpose

Trace uses AI to help users understand software repositories.

AI is not used as the primary source of truth.

The AI system must:

- extract deterministic facts first
- derive graph-based signals
- infer higher-level concepts only when useful
- attach evidence to every inferred result
- expose uncertainty
- avoid unsupported claims
- remain provider-neutral
- support evaluation against simpler baselines

Core rule:

> Evidence before inference.

---

## 2. AI System Goals

## 2.1 Repository Understanding

Generate useful knowledge about:

- architecture
- subsystems
- dependencies
- decisions
- evolution
- contributors
- learning order

## 2.2 Explainability

Every inferred output must expose:

- confidence
- evidence
- provenance
- generator version
- model version
- prompt version
- generation timestamp

## 2.3 Reliability

The system must fail safely.

If AI generation fails:

- deterministic repository knowledge remains available
- failed sections become partial
- no fabricated fallback content appears

## 2.4 Replaceability

Trace must support multiple:

- LLM providers
- embedding providers
- rerankers
- parser implementations
- retrieval strategies

## 2.5 Evaluability

Every major AI component must support:

- offline test data
- measurable outputs
- baseline comparison
- versioned results
- reproducible repository snapshots

---

## 3. System Boundary

AI system begins after repository validation.

```text
GitHub Repository
    ↓
Artifact Ingestion
    ↓
Source Parsing
    ↓
Ontology Construction
    ↓
Deterministic Knowledge Graph
    ↓
Graph Analysis
    ↓
Embeddings
    ↓
Semantic Enrichment
    ↓
Evidence Verification
    ↓
Software Atlas
    ↓
Adaptive Question Answering
```

---

## 4. Knowledge Processing Layers

Trace processes knowledge in four layers.

## 4.1 Raw Artifact Layer

Inputs:

- repository metadata
- source files
- issues
- pull requests
- commits
- releases
- discussions
- contributor events
- dependency manifests

No AI interpretation.

## 4.2 Structural Layer

Deterministically extracted:

- directory containment
- file containment
- symbol declarations
- imports
- dependency declarations
- commit-file changes
- pull-request relations
- issue references
- authorship
- reviews
- release membership

## 4.3 Analytical Layer

Deterministically derived:

- PageRank
- degree centrality
- betweenness centrality
- connected components
- graph communities
- dependency cycles
- co-change frequency
- contributor activity scores

## 4.4 Semantic Layer

AI-assisted:

- subsystem names
- subsystem summaries
- architecture summaries
- design decisions
- topics
- learning steps
- question answers

Semantic outputs must reference lower-layer evidence.

---

## 5. Pipeline Stages

```text
validate
fetch_metadata
fetch_source_tree
fetch_issues
fetch_pull_requests
fetch_commits
fetch_releases
fetch_contributors
normalize
parse_source
build_graph
analyze_graph
generate_embeddings
discover_subsystems
extract_decisions
analyze_contributors
generate_learning_order
generate_atlas
verify_outputs
finalize
```

Each stage stores:

- status
- progress
- input version
- output version
- attempt count
- start time
- finish time
- error
- output summary

---

## 6. Artifact Ingestion

## 6.1 Inputs

Trace fetches:

- repository metadata
- default branch HEAD
- source tree
- text file contents
- issues
- pull requests
- pull-request files
- reviews when available
- commits
- commit changed files
- releases
- contributors
- discussions when available
- labels
- dependency manifests

## 6.2 Normalization

Provider objects are converted into internal domain models.

Example:

```text
GitHub PullRequest response
    ↓
NormalizedPullRequest
    ↓
PullRequest ontology entity
```

GitHub SDK-specific structures must not leak into later stages.

## 6.3 Content Selection

Skip or reduce processing for:

- binary files
- vendored code
- generated files
- lock files
- large data files
- minified assets
- build output
- dependency directories

Common exclusions:

```text
node_modules/
dist/
build/
coverage/
.venv/
venv/
vendor/
__pycache__/
*.min.js
package-lock.json
pnpm-lock.yaml
yarn.lock
uv.lock
```

Lock files may still be used for dependency metadata.

---

## 7. Source Parsing

## 7.1 Supported Languages

MVP:

- Python
- TypeScript
- JavaScript

Reduced analysis:

- unsupported text-based languages
- configuration files
- Markdown
- manifests

## 7.2 Extracted Facts

Parsers may extract:

- module
- class
- function
- method
- interface
- type
- enum
- React component
- React hook
- route
- import
- export
- inheritance
- implementation
- basic call reference
- docstring
- comments where useful

## 7.3 Parser Output

```json
{
  "file_path": "backend/src/auth/service.py",
  "language": "Python",
  "symbols": [],
  "imports": [],
  "calls": [],
  "parse_status": "success",
  "parser_name": "python_parser",
  "parser_version": "1.0.0"
}
```

## 7.4 Reliability Rules

- `IMPORTS` requires parsed import evidence.
- `CALLS` requires parsed call evidence.
- import does not imply runtime call.
- unresolved target remains unresolved.
- parser failure does not abort full ingestion.
- generic file representation remains available.

---

## 8. Repository Graph Construction

## 8.1 Deterministic Nodes

Examples:

- Repository
- RepositorySnapshot
- Directory
- File
- Symbol
- Issue
- PullRequest
- Commit
- Release
- Discussion
- Person
- Label
- ExternalDependency

## 8.2 Deterministic Edges

Examples:

- `CONTAINS`
- `DECLARES`
- `IMPORTS`
- `CALLS`
- `EXTENDS`
- `IMPLEMENTS`
- `MODIFIES`
- `REFERENCES`
- `AUTHORED`
- `REVIEWED`
- `RESOLVES`
- `RELEASE_INCLUDES`
- `LABELED_WITH`
- `PARENT_OF`

## 8.3 Edge Provenance

Every edge stores:

- extraction method
- source entity
- source span when available
- parser/provider version
- snapshot
- confidence when non-exact

---

## 9. Graph Analysis

NetworkX performs in-memory graph analysis.

## 9.1 PageRank

Purpose:

Identify structurally important files or symbols.

Use carefully.

High PageRank means graph importance, not business importance.

## 9.2 Degree Centrality

Purpose:

Identify highly connected nodes.

## 9.3 Betweenness Centrality

Purpose:

Identify bridge nodes between communities.

Potential interpretation:

- integration point
- shared infrastructure
- architectural boundary

Must remain labeled as graph-derived.

## 9.4 Connected Components

Purpose:

Find isolated or weakly connected areas.

## 9.5 Community Detection

Purpose:

Generate candidate subsystem clusters.

Potential algorithms:

- greedy modularity
- Louvain when dependency added
- label propagation

MVP may begin with NetworkX greedy modularity.

## 9.6 Dependency Cycles

Purpose:

Identify circular dependencies.

## 9.7 Co-Change Analysis

Files modified together may indicate:

- subsystem membership
- cross-cutting concern
- hidden coupling

Co-change does not prove runtime dependency.

---

## 10. Embedding System

## 10.1 Embedding Targets

Generate embeddings for:

- README and documentation chunks
- source summaries
- symbol summaries
- issue titles and bodies
- pull-request titles and bodies
- discussion content
- release notes
- subsystem summaries
- decision summaries
- evidence excerpts

## 10.2 Raw Source Strategy

Do not blindly embed entire large files.

Preferred source representation:

```text
file metadata
+ symbol list
+ docstrings
+ bounded source chunks
+ generated deterministic summary
```

## 10.3 Chunking

Chunking must preserve:

- source entity
- file path
- line range
- artifact ID
- repository snapshot
- section heading when present

Suggested limits:

```text
target tokens: 400–800
overlap: 50–100
```

Exact settings require evaluation.

## 10.4 Content Hashing

Embedding cache key:

```text
content_hash
+ embedding_model
+ embedding_model_version
+ chunking_version
```

Unchanged content must not be embedded again.

## 10.5 Provider Interface

```python
from typing import Protocol

class EmbeddingProvider(Protocol):
    async def embed_documents(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        ...

    async def embed_query(
        self,
        text: str,
    ) -> list[float]:
        ...
```

## 10.6 Provider Strategy

Support:

- one hosted provider
- one local/free provider when practical

Local examples may include sentence-transformer models.

Hosted provider remains configurable.

No product logic may depend on one provider.

---

## 11. Semantic Document Model

Every embedded document stores:

```text
id
repository_id
snapshot_id
source_entity_id
document_type
chunk_index
chunk_text
token_count
content_hash
embedding_model
embedding_version
metadata
```

Document types:

```text
documentation
source
symbol
issue
pull_request
discussion
release
decision
subsystem
evidence
```

---

## 12. Subsystem Discovery

Subsystem discovery combines deterministic and probabilistic signals.

## 12.1 Input Signals

- directory structure
- import graph communities
- dependency graph communities
- semantic similarity
- file naming
- symbol naming
- documentation headings
- issue labels
- pull-request topics
- co-change patterns

## 12.2 Discovery Workflow

```text
Build candidate file graph
    ↓
Run graph community detection
    ↓
Compare directory boundaries
    ↓
Calculate semantic cohesion
    ↓
Add historical/co-change signals
    ↓
Create candidate clusters
    ↓
LLM labels and summarizes clusters
    ↓
Verify cluster evidence
    ↓
Persist confirmed/candidate subsystems
```

## 12.3 Candidate Cluster

```json
{
  "cluster_id": "cluster_7",
  "files": [],
  "directories": [],
  "symbols": [],
  "graph_modularity": 0.71,
  "semantic_cohesion": 0.83,
  "directory_cohesion": 0.76,
  "historical_cohesion": 0.64
}
```

## 12.4 Subsystem Labeling Prompt Input

Include:

- candidate file paths
- important symbols
- central files
- external dependencies
- common terms
- documentation references
- related issues and pull requests

Do not include entire repository.

## 12.5 Structured Output

```json
{
  "name": "Authentication",
  "summary": "Handles identity, tokens, and access validation.",
  "confidence": 0.86,
  "rationale": "Files form an import community...",
  "key_files": [],
  "evidence_ids": []
}
```

## 12.6 Confidence

Example conceptual formula:

```text
subsystem_confidence =
    0.30 × graph_cohesion
  + 0.20 × directory_cohesion
  + 0.20 × semantic_cohesion
  + 0.15 × historical_cohesion
  + 0.15 × label_confidence
```

Weights are initial hypotheses.

They must be evaluated.

## 12.7 Display Rules

- high confidence: confirmed subsystem
- medium confidence: confirmed with visible uncertainty
- low confidence: candidate subsystem
- weak cluster: do not promote to Overview

---

## 13. Architecture Synthesis

Architecture synthesis explains system structure from graph evidence.

## 13.1 Inputs

- confirmed subsystems
- subsystem dependencies
- central files
- entry points
- external dependencies
- framework metadata
- graph metrics
- repository documentation

## 13.2 Output

```json
{
  "summary": "The system is organized around...",
  "architectural_style": [
    "modular backend",
    "single-page frontend"
  ],
  "entry_points": [],
  "major_components": [],
  "external_dependencies": [],
  "confidence": 0.82,
  "evidence_ids": []
}
```

## 13.3 Rules

- architecture style must be labeled inferred
- no runtime claims from imports alone
- no microservice claim from directories alone
- no framework claim without dependency/source evidence
- each major component links to graph entities

---

## 14. Decision Extraction

Decision extraction identifies why meaningful changes occurred.

## 14.1 Preferred Evidence Sources

Ranked:

1. explicit architecture decision record
2. discussion with clear resolution
3. issue plus implementing pull request
4. pull-request description plus review discussion
5. release note plus linked pull request
6. commit message plus surrounding artifacts

A commit message alone is weak evidence.

## 14.2 Candidate Generation

Potential candidates come from:

- issue labels
- PR titles
- phrases such as “choose”, “replace”, “migrate”, “introduce”
- linked issue/PR chains
- major dependency changes
- broad co-change events
- release notes
- discussions

## 14.3 Extraction Workflow

```text
Find candidate artifact cluster
    ↓
Build evidence chain
    ↓
Retrieve relevant text
    ↓
Extract context, decision, alternatives, outcome
    ↓
Validate source references
    ↓
Score confidence
    ↓
Persist candidate or confirmed decision
```

## 14.4 Structured Output

```json
{
  "title": "Introduce Redis-backed retry coordination",
  "context": "Background jobs required shared retry state.",
  "decision": "Use Redis to coordinate retry state.",
  "alternatives": [],
  "outcome": "Workers can share retry information.",
  "status": "confirmed",
  "confidence": 0.84,
  "evidence_ids": []
}
```

## 14.5 Confirmation Rules

Confirmed decision requires:

- at least one non-model evidence source
- identifiable context
- identifiable chosen action
- evidence chain
- confidence above threshold
- no stronger contradiction

## 14.6 Insufficient Evidence

When evidence is incomplete:

```json
{
  "status": "insufficient_evidence",
  "confidence": 0.43
}
```

Do not display as confirmed history.

---

## 15. Topic Extraction

Topics connect repository concepts across artifact types.

Examples:

- authentication
- migrations
- caching
- retry handling
- dependency injection

Inputs:

- embeddings
- labels
- repeated terms
- subsystem membership
- issue/PR clustering

Topics support:

- search
- retrieval
- Explore graph
- decision grouping

---

## 16. Contributor Intelligence

Contributor intelligence estimates repository-backed activity.

## 16.1 Signals

- authored pull requests
- reviewed pull requests
- commits
- files modified
- subsystem file activity
- recency
- repeated contribution
- issue participation later

## 16.2 Example Score

```text
expertise_score =
    0.30 × authored_pr_score
  + 0.20 × reviewed_pr_score
  + 0.15 × commit_score
  + 0.20 × subsystem_file_score
  + 0.15 × recency_score
```

Weights are configurable and evaluable.

## 16.3 Recency Decay

Example:

```text
recency_weight = exp(-days_since_activity / decay_constant)
```

Exact decay constant belongs in evaluation config.

## 16.4 Language Rules

Allowed:

```text
Repository evidence suggests strong activity in authentication.
```

Not allowed:

```text
This person is the authentication expert.
```

---

## 17. Learning Order Generation

Learning order helps users navigate unfamiliar repositories.

## 17.1 Signals

- entry points
- subsystem dependencies
- centrality
- documentation order
- complexity
- prerequisite relationships

## 17.2 Workflow

```text
Identify entry points
    ↓
Build subsystem dependency DAG where possible
    ↓
Estimate complexity
    ↓
Rank foundational subsystems
    ↓
Generate recommended order
    ↓
Attach rationale and evidence
```

## 17.3 Output

```json
{
  "steps": [
    {
      "order": 1,
      "title": "Start with request routing",
      "target_entity_id": "subsystem_uuid",
      "rationale": "Most request paths enter here.",
      "confidence": 0.79,
      "evidence_ids": []
    }
  ]
}
```

This is guidance, not repository fact.

---

## 18. Atlas Generation

Atlas generation creates persistent product sections.

## 18.1 Overview

Inputs:

- repository metadata
- language distribution
- major subsystems
- architecture summary
- releases
- decisions
- learning order

## 18.2 Architecture

Inputs:

- subsystem graph
- central nodes
- entry points
- dependencies
- graph metrics

## 18.3 Subsystems

Inputs:

- cluster membership
- labels
- summaries
- evidence
- historical activity

## 18.4 Timeline

Primarily deterministic.

AI may summarize groups of events.

## 18.5 Decisions

Evidence-backed extracted decisions.

## 18.6 Contributors

Derived metrics plus cautious summaries.

## 18.7 Explore

Raw and inferred graph.

## 18.8 Ask

Generated per query.

Not persisted as Atlas section in MVP unless query history is enabled.

---

## 19. Query Intent Classification

Supported intents:

```text
overview
architecture
subsystem
decision
historical
contributor
file
symbol
semantic_search
mixed
```

Classifier input:

- question
- repository context
- optional active screen
- optional filters

Classifier output:

```json
{
  "intent": "decision",
  "confidence": 0.91,
  "entities": [
    {
      "type": "ExternalDependency",
      "value": "Redis"
    }
  ],
  "requires_graph": true,
  "requires_vector": true,
  "requires_metadata": true
}
```

A simple deterministic classifier may handle obvious patterns first.

LLM classification used only when needed.

---

## 20. Retrieval Modes

## 20.1 Metadata Retrieval

Use for:

- stars
- release dates
- issue state
- contributor counts
- exact artifact lookups

## 20.2 Vector Retrieval

Use for:

- semantic similarity
- issue/PR meaning
- documentation
- broad conceptual questions

## 20.3 Graph Retrieval

Use for:

- dependencies
- artifact chains
- contributor-subsystem relationships
- decision implementation paths
- related files

## 20.4 Adaptive Hybrid Retrieval

Combines multiple modes.

Example:

Question:

```text
Why was Redis introduced, and which files depend on it?
```

Plan:

```text
metadata → find Redis dependency
vector → find discussion and PR context
graph → follow decision → PR → commits → files
```

---

## 21. Retrieval Planning

Retrieval planner produces:

```json
{
  "intent": "mixed",
  "steps": [
    {
      "type": "metadata",
      "query": "Redis dependency"
    },
    {
      "type": "vector",
      "query": "reason Redis introduced"
    },
    {
      "type": "graph",
      "start_entities": [],
      "edge_types": [
        "DERIVED_FROM",
        "IMPLEMENTED_BY",
        "MODIFIES",
        "DEPENDS_ON"
      ],
      "max_depth": 3
    }
  ]
}
```

Planner must respect limits:

- max vector results
- max graph depth
- max graph nodes
- max evidence items
- token budget

---

## 22. Vector Retrieval

## 22.1 Query

Generate query embedding.

## 22.2 Filter

Filter by:

- repository ID
- snapshot ID
- document type
- subsystem
- date range
- artifact type

## 22.3 Similarity

Use pgvector cosine distance or selected operator.

## 22.4 Result

```json
{
  "document_id": "doc_uuid",
  "source_entity_id": "pr_uuid",
  "score": 0.88,
  "chunk_text": "Redis was introduced...",
  "metadata": {}
}
```

## 22.5 Diversity

Use deduplication or MMR-style selection to avoid near-identical chunks.

---

## 23. Graph Retrieval

Graph retrieval starts from resolved entities.

Example:

```text
Redis
    ↓ DEPENDS_ON
Subsystem
    ↓ AFFECTS
Decision
    ↓ IMPLEMENTED_BY
PullRequest
    ↓ CONTAINS
Commit
    ↓ MODIFIES
File
```

Controls:

- allowed edge types
- max depth
- max nodes
- confidence threshold
- knowledge-kind filter

Graph paths become evidence.

---

## 24. Reranking

Initial reranking may combine:

```text
final_score =
    semantic_similarity
  + graph_proximity
  + source_quality
  + recency
  + exact_match
  + evidence_strength
```

Possible normalized formula:

```text
0.35 semantic
0.25 graph
0.15 source quality
0.10 recency
0.10 exact match
0.05 evidence strength
```

Weights require evaluation.

Future:

- cross-encoder reranker
- hosted reranking model

---

## 25. Context Assembly

Context builder must:

- group evidence by source
- deduplicate chunks
- preserve citations
- preserve graph paths
- prioritize high-quality evidence
- fit token budget
- include limitations
- separate facts from inferences

Context blocks:

```text
Repository facts
Graph evidence
Text evidence
Existing inferred knowledge
Uncertainty notes
```

---

## 26. Ask Workflow

LangGraph workflow:

```text
validate_question
    ↓
classify_intent
    ↓
resolve_entities
    ↓
plan_retrieval
    ↓
retrieve_metadata
    ↓
retrieve_vectors
    ↓
expand_graph
    ↓
rerank_evidence
    ↓
assemble_context
    ↓
generate_answer
    ↓
verify_citations
    ↓
calculate_confidence
    ↓
return_response
```

---

## 27. LangGraph State

Example state:

```python
class QueryState(TypedDict):
    repository_id: str
    snapshot_id: str
    question: str
    intent: str | None
    entities: list[dict]
    retrieval_plan: list[dict]
    metadata_results: list[dict]
    vector_results: list[dict]
    graph_results: list[dict]
    ranked_evidence: list[dict]
    answer: dict | None
    verification: dict | None
    errors: list[dict]
```

State must remain serializable.

---

## 28. Answer Generation

The answer model must produce structured output.

```json
{
  "answer": "Redis appears to have been introduced...",
  "claims": [
    {
      "text": "Redis coordinates retry state.",
      "evidence_ids": ["evidence_uuid"],
      "confidence": 0.82
    }
  ],
  "limitations": [],
  "possible_interpretations": [],
  "related_files": [],
  "related_decisions": [],
  "timeline_events": []
}
```

Temperature:

```text
0 or near 0
```

Creative variation is not useful.

---

## 29. Citation Verification

Citation verification is mandatory.

## 29.1 Verify Existence

Every cited evidence ID must exist.

## 29.2 Verify Repository Scope

Evidence must belong to current repository and snapshot.

## 29.3 Verify Entailment

Each claim must be supported by cited evidence.

Initial verification may use:

- deterministic checks
- lexical overlap
- entity matching
- secondary LLM verifier

## 29.4 Remove Unsupported Claims

Unsupported claims must be:

- removed
- downgraded to inference
- moved to limitations
- regenerated once when safe

## 29.5 Verification Output

```json
{
  "passed": true,
  "claims": [
    {
      "claim": "Redis coordinates retry state.",
      "supported": true,
      "evidence_ids": ["evidence_uuid"]
    }
  ]
}
```

---

## 30. Answer Confidence

Answer confidence combines:

- evidence quality
- evidence agreement
- retrieval score
- citation verification
- source diversity
- inference depth
- contradiction penalty

Example conceptual formula:

```text
answer_confidence =
    evidence_quality
  + retrieval_strength
  + source_diversity
  + verification_score
  - contradiction_penalty
  - inference_depth_penalty
```

Confidence is operational, not calibrated probability unless later validated.

---

## 31. Insufficient-Evidence Behavior

Never return only:

```text
No data.
```

Return:

- what could not be confirmed
- closest evidence
- related files
- related artifacts
- possible interpretation labeled as inference
- suggested next question

Example:

```json
{
  "answer": "Trace could not confirm the original reason Redis was introduced.",
  "confidence": 0.41,
  "limitations": [
    "No explicit decision record was found."
  ],
  "possible_interpretations": [
    {
      "text": "Redis may have been added for retry coordination.",
      "confidence": 0.58,
      "label": "inference"
    }
  ],
  "evidence": []
}
```

---

## 32. Contradiction Handling

Potential contradictions:

- issue proposes one solution
- PR implements another
- release notes describe changed outcome
- older docs conflict with current code

Rules:

- prefer later implemented evidence for current behavior
- preserve historical proposal separately
- mark disagreement
- avoid collapsing multiple viewpoints
- expose timeline

---

## 33. Prompt Design

Prompt templates are versioned.

Each prompt includes:

- task
- strict output schema
- repository content boundaries
- evidence IDs
- prohibited behavior
- uncertainty rules

Example structure:

```text
SYSTEM RULES
TASK
OUTPUT SCHEMA
EVIDENCE
REPOSITORY CONTENT — UNTRUSTED
```

Repository content must be explicitly labeled untrusted.

---

## 34. Prompt Injection Defense

Repository text may contain malicious instructions.

Controls:

- never treat repository content as system instruction
- quote or delimit untrusted content
- use structured outputs
- reject unknown schema fields
- deny tool-control instructions from repository content
- limit model tools
- verify evidence independently
- log suspicious instruction patterns
- never expose secrets in prompts

---

## 35. Structured Output Validation

Every model response must pass Pydantic validation.

Failure handling:

1. parse
2. validate
3. retry once with validation error
4. fail stage or downgrade output

Never persist malformed model output.

---

## 36. Provider Interfaces

## 36.1 LLM Provider

```python
class LLMProvider(Protocol):
    async def generate_structured(
        self,
        *,
        messages: list[dict],
        schema: type[BaseModel],
        temperature: float = 0,
        timeout_seconds: int = 60,
    ) -> BaseModel:
        ...
```

## 36.2 Embedding Provider

```python
class EmbeddingProvider(Protocol):
    async def embed_documents(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        ...

    async def embed_query(
        self,
        text: str,
    ) -> list[float]:
        ...
```

## 36.3 Reranker

```python
class Reranker(Protocol):
    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int,
    ) -> list[float]:
        ...
```

---

## 37. Provider Selection

Configuration:

```text
LLM_PROVIDER
LLM_MODEL
EMBEDDING_PROVIDER
EMBEDDING_MODEL
RERANKER_PROVIDER
RERANKER_MODEL
```

Selection rules:

- explicit configuration
- no silent model switching
- provider/model stored with outputs
- unsupported configuration fails startup

---

## 38. Local and Free Model Strategy

Trace should support low-cost development.

Possible uses for local/free models:

- embeddings
- basic classification
- topic clustering
- development tests

Hosted model may remain necessary for:

- high-quality decision extraction
- architecture synthesis
- final QA reasoning

Provider quality must be evaluated, not assumed.

---

## 39. Cost Controls

Controls:

- content hashing
- embedding reuse
- batch embeddings
- bounded context
- model selection by task
- caching
- deterministic classification first
- token logging
- per-job cost estimates
- stage budgets

Track:

- input tokens
- output tokens
- embedding tokens
- calls
- estimated cost
- cache hits

---

## 40. Latency Controls

- parallel independent GitHub fetches
- batch embeddings
- cache repeated retrieval
- bounded graph expansion
- small structured prompts
- async provider calls
- pre-generated Atlas summaries
- streaming answer later

Target Ask latency:

```text
under 15 seconds for supported queries
```

---

## 41. Model Failure Handling

## 41.1 Timeout

- retry with backoff
- preserve stage state
- mark provider timeout

## 41.2 Rate Limit

- respect retry-after
- delay stage
- expose retryable state

## 41.3 Invalid Output

- validation retry once
- fail specific inference
- preserve deterministic output

## 41.4 Provider Outage

- mark Atlas partial
- allow later retry
- no fake fallback

---

## 42. AI Observability

Structured logs:

- repository ID
- snapshot ID
- workflow
- stage
- provider
- model
- prompt version
- latency
- token usage
- retry count
- validation result
- verification result
- error code

Do not log:

- secrets
- complete sensitive prompts
- provider tokens

MVP only uses public repositories, but safe logging still applies.

---

## 43. AI Data Versioning

Version independently:

- parser
- ontology
- graph builder
- graph algorithm
- chunking
- embedding model
- subsystem generator
- decision extractor
- prompt
- LLM
- verifier
- Atlas generator

Example:

```json
{
  "ontology_version": "1.0.0",
  "parser_version": "1.1.0",
  "embedding_model": "model-name",
  "embedding_version": "2026-01",
  "prompt_version": "decision-v3",
  "generator_version": "0.4.0"
}
```

---

## 44. Reproducibility

A result should be reproducible from:

- repository ID
- snapshot commit SHA
- ontology version
- parser version
- graph algorithm version
- embedding model/version
- model/version
- prompt version
- generation config

Exact output may still vary for nondeterministic hosted models.

Use:

```text
temperature = 0
```

where supported.

---

## 45. Evaluation Hooks

Every workflow must expose intermediate data.

For Ask:

- intent
- retrieval plan
- vector results
- graph results
- reranked evidence
- generated claims
- verification result
- final answer

For subsystem discovery:

- candidate clusters
- signal scores
- labels
- confidence
- evidence

For decisions:

- candidate artifacts
- evidence chain
- extracted fields
- status
- confidence

---

## 46. Baselines

Trace must compare:

## 46.1 Keyword Retrieval

No embeddings.

No graph.

## 46.2 Vector-Only RAG

Embeddings plus generation.

No graph traversal.

## 46.3 Graph Retrieval

Graph evidence plus generation.

No vector retrieval.

## 46.4 Adaptive Hybrid

Metadata + vector + graph.

Main Trace system.

---

## 47. AI Metrics

## 47.1 Retrieval

- context precision
- context recall
- mean reciprocal rank
- hit rate
- evidence coverage

## 47.2 Generation

- faithfulness
- answer relevance
- citation correctness
- claim support rate
- unsupported claim rate

## 47.3 Graph

- edge precision
- edge recall
- path correctness
- subsystem coherence
- subsystem stability

## 47.4 Decisions

- decision precision
- decision recall
- context correctness
- outcome correctness
- evidence-chain completeness

## 47.5 Operations

- latency
- token use
- cost
- failure rate
- cache hit rate

---

## 48. Human Evaluation

Human evaluators compare:

```text
GitHub + README
vs.
Trace
```

Tasks:

- identify architecture
- identify subsystem
- explain decision
- find implementation files
- identify active contributors
- trace project evolution

Measure:

- correctness
- completion time
- confidence
- perceived understanding
- evidence usefulness

---

## 49. Test Strategy

## 49.1 Unit Tests

- chunking
- prompt schemas
- confidence bands
- retrieval routing
- score calculations
- evidence validation
- provider adapters

## 49.2 Golden Tests

Fixed repository snapshot + expected structured output.

Examples:

- expected entities
- expected edges
- expected subsystem candidates
- expected decision evidence

## 49.3 Regression Tests

Prevent:

- citation loss
- unsupported confidence increase
- duplicate entities
- changed retrieval plan
- schema break

## 49.4 Mock Provider Tests

Use deterministic fake providers.

No external model required for normal CI.

## 49.5 Live Provider Tests

Optional/manual.

Not required on every PR.

---

## 50. Quality Gates

An inferred output may be published only when:

- structured output valid
- evidence IDs exist
- evidence belongs to repository
- confidence calculated
- provenance stored
- verification completed
- status allowed for UI

Confirmed decision additionally requires:

- non-model evidence
- complete decision statement
- evidence chain
- no unresolved contradiction

---

## 51. MVP AI Deliverables

## P0

- deterministic ingestion
- source parsing
- ontology entities
- graph construction
- embeddings
- basic vector retrieval
- cited Ask answer
- evidence validation

## P1

- subsystem discovery
- architecture summary
- decision extraction
- contributor scoring
- adaptive retrieval
- graph paths
- citation verification
- evaluation harness

## P2

- advanced reranker
- contradiction detector
- local LLM option
- calibrated confidence
- incremental regeneration
- learning-order refinement

---

## 52. Non-Goals

MVP AI system does not attempt:

- perfect code understanding
- runtime execution modeling
- full call graph for all languages
- formal program verification
- autonomous code changes
- guaranteed architectural truth
- replacement of maintainer judgment
- hidden chain-of-thought exposure

Trace returns conclusions and evidence, not private model reasoning.

---

## 53. Definition of AI System Success

AI system succeeds when:

- deterministic facts are extracted reliably
- inferred outputs remain evidence-backed
- unsupported claims are removed or labeled
- partial failures preserve useful Atlas data
- provider changes do not affect product interfaces
- adaptive retrieval beats vector-only baseline on target tasks
- outputs remain inspectable and reproducible
- users understand uncertainty

---

## 54. Final AI System Summary

```text
Repository artifacts
    ↓
Deterministic extraction
    ↓
Repository ontology
    ↓
Knowledge graph
    ↓
Graph analysis
    ↓
Embeddings
    ↓
Evidence-backed inference
    ↓
Adaptive retrieval
    ↓
Structured reasoning
    ↓
Citation verification
    ↓
Software Atlas
```

Final rule:

> AI may organize, connect, summarize, and infer repository knowledge. It may never present unsupported inference as confirmed software truth.
