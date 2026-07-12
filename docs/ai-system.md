# Trace — AI System

## Principle

AI may organize, summarize, connect, and infer repository knowledge.

It may not present unsupported inference as confirmed truth.

## Pipeline

```text
GitHub artifacts
→ deterministic extraction
→ ontology
→ knowledge graph
→ graph analysis
→ embeddings
→ semantic enrichment
→ evidence verification
→ Software Atlas
→ adaptive Ask
```

## Deterministic Layer

Extract:

- source tree
- files
- symbols
- imports
- dependencies
- issues
- pull requests
- commits
- releases
- contributors
- reviews
- artifact links

Supported languages:

- Python
- TypeScript
- JavaScript

Rules:

- import does not imply runtime call
- unresolved references remain unresolved
- parser failure must not abort full ingestion

## Graph Analysis

Use NetworkX for:

- connected components
- centrality
- PageRank
- community detection
- dependency cycles
- bridge nodes
- co-change signals

Graph metrics are derived, not facts about business importance.

## Embeddings

Embed:

- documentation
- source summaries
- symbols
- issues
- pull requests
- discussions
- release notes
- subsystem summaries
- decision evidence

Chunk metadata must preserve:

- source entity
- path
- line range
- artifact ID
- snapshot
- content hash

Reuse embeddings when content hash + model + chunk version match.

## Subsystem Discovery

Signals:

- import communities
- directory boundaries
- semantic cohesion
- naming
- docs
- labels
- co-change history

Workflow:

```text
candidate clusters
→ score signals
→ LLM names/summarizes
→ verify evidence
→ persist confirmed/candidate subsystem
```

Low-confidence subsystems stay candidates.

## Architecture Synthesis

Inputs:

- confirmed subsystems
- subsystem dependencies
- central files
- entry points
- external dependencies
- docs

Rules:

- no microservice claim from folders alone
- no runtime claim from imports alone
- every major component links to evidence

## Decision Extraction

Preferred sources:

1. ADR
2. discussion with clear resolution
3. issue + implementing PR
4. PR description/review
5. release note + linked PR
6. commit context

Workflow:

```text
find candidate artifact cluster
→ build evidence chain
→ extract context/decision/outcome
→ verify sources
→ score confidence
→ persist candidate/confirmed decision
```

Confirmed decision requires non-model evidence.

## Contributor Intelligence

Signals:

- authored PRs
- reviewed PRs
- commits
- subsystem files
- recency

Example:

```text
score =
0.30 authored PRs
+ 0.20 reviews
+ 0.15 commits
+ 0.20 subsystem files
+ 0.15 recency
```

Weights remain configurable and evaluable.

## Retrieval Modes

### Metadata

Best for:

- stats
- dates
- exact artifact lookup

### Vector

Best for:

- semantic similarity
- docs
- issue/PR meaning

### Graph

Best for:

- dependencies
- ownership paths
- decision implementation
- artifact chains

### Adaptive Hybrid

Combines modes based on question intent.

## Ask Workflow

```text
validate question
→ classify intent
→ resolve entities
→ plan retrieval
→ metadata retrieval
→ vector retrieval
→ graph expansion
→ rerank evidence
→ assemble context
→ generate structured answer
→ verify citations
→ calculate confidence
```

## Structured Answer

Must return:

- answer
- confidence
- claims
- evidence
- citations
- graph path
- related files
- related decisions
- timeline events
- limitations
- labeled interpretations
- suggested follow-up

## Citation Verification

Verify:

- evidence exists
- evidence belongs to repository/snapshot
- claim is supported
- citation points to correct source

Unsupported claims must be:

- removed
- downgraded to inference
- moved to limitations
- regenerated once when safe

## Insufficient Evidence

Do not return only:

```text
No data.
```

Return:

- what cannot be confirmed
- closest evidence
- related files/artifacts
- possible interpretation labeled as inference
- suggested next question

## Provider Interfaces

```python
class EmbeddingProvider(Protocol):
    async def embed_documents(self, texts): ...
    async def embed_query(self, text): ...

class LLMProvider(Protocol):
    async def generate_structured(self, *, messages, schema): ...
```

Support at least:

- one hosted provider
- one local/free embedding option when practical

## Prompt Safety

Repository content is untrusted.

Controls:

- strict prompt boundaries
- structured outputs
- schema validation
- no tool instructions from repo content
- evidence verification
- no secret exposure

## Versioning

Store:

- parser version
- ontology version
- graph algorithm version
- chunking version
- embedding model/version
- LLM model/version
- prompt version
- verifier version
- Atlas generator version

## Baselines

Compare:

- keyword
- vector-only
- graph-only
- adaptive hybrid

## Quality Gates

Publish inferred output only when:

- schema valid
- confidence present
- provenance stored
- evidence exists
- verification completed
- status allowed for UI
