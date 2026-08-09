# Week 4 — Core Software Atlas

Week 4 is complete. Trace now turns its deterministic repository graph into an
evidence-backed Software Atlas with semantic documents, embeddings, cautious
subsystem inference, architecture facts, and browsable Atlas screens.

## Documents Are Chunks

Each `documents` row is one retrievable, evidence-preserving chunk rather than
an entire source artifact. A document stores:

- repository and immutable repository-version scope;
- source type, stable source key, and idempotent canonical key;
- optional source graph node, URL, title, and source metadata;
- chunk index, token count, character offsets, and content;
- a SHA-256 content hash, provenance, and ontology version.

The identity `(repository_version_id, canonical_key)` makes repeated chunking
safe. Updating chunk content changes its content hash without silently treating
an older embedding as current.

## Embedding Spaces

`embedding_spaces` records the provider, model, optional model revision,
dimensions, distance metric, provenance, and active state. The MVP permits one
active space and standardizes on 384-dimensional cosine vectors so hosted and
local adapters can share one indexed schema.

Activating a space deactivates the previous one in the same transaction.
Embedding-space configuration is separate from document data so vectors can
be rebuilt or migrated without re-chunking source material.

## pgvector Embeddings

`embeddings` stores one vector per document and embedding space. It repeats the
repository and snapshot keys for bounded retrieval filters and copies the
document content hash used during generation. Retrieval excludes an embedding
when that hash no longer matches the current document, and the pending-work
query returns missing or stale documents for re-embedding.

The vector column is `vector(384)` with an HNSW cosine index. Repository reads
cap nearest-neighbor results at 100 and pending-document batches at 1,000.
Zero, non-finite, or incorrectly sized vectors fail before persistence.

## Repository Documentation Chunking

The deterministic `documentation-v1` chunker reads persisted files classified
as documentation, including README, Markdown, MDX, reStructuredText, text, and
AsciiDoc sources. It prefers heading and paragraph boundaries, caps chunks at
2,400 characters, and handles oversized unbroken lines without dropping
content.

Every chunk preserves its source path, source-file and graph-node identity,
blob SHA, source content hash, fixed-snapshot GitHub URL, heading context,
character offsets, and one-based line range. Canonical chunk keys are bounded
hashes of path, chunk index, and chunker version, making rebuilds idempotent
even for maximum-length repository paths.

The `chunk_repository_documentation` ingestion stage runs after deterministic
graph analysis. It is transactionally resumable under the existing stage
runner: completed stages are skipped, failed writes roll back, and the stage
summary records files, chunks, characters, empty files, stale rows, and the
chunker version. Rebuilding prunes obsolete documentation chunks and their
cascading embeddings.

## GitHub Artifact Documents

Issues, pull requests, and release notes are converted into snapshot-scoped
semantic documents after the historical graph is available. Artifact bodies
use the same bounded, heading-aware chunking rules as repository docs. When a
body is absent, the issue or pull-request title, or the release tag, becomes a
small fallback document instead of silently dropping the artifact.

Each chunk retains its provider record ID, issue or pull-request number,
release tag, state flags, relevant commit SHAs, timestamps, provider URL,
content field, source-content hash, and repository-scoped historical graph
node. Character offsets and line ranges always refer to the explicitly named
source field.

The resumable `chunk_repository_artifacts` stage replaces each artifact
document family independently. Re-ingestion updates stable chunk identities
and removes documents and cascading embeddings for artifacts that are no
longer present in the bounded provider snapshot.

## Deterministic Source Summaries

Source and test files receive compact summaries generated entirely from
persisted parser and graph facts. Each summary names the file kind, language,
blob and content hashes, declared symbols, internal file imports, external
dependencies, degree centrality, and import-community membership. No model is
used, so rebuilding the same snapshot produces the same text and identity.

Relation lists are sorted and capped at 50 declarations and 50 imports per
file, with explicit omission counts. Labels are normalized and bounded, and a
snapshot is capped at 10,000 eligible files. Generated summaries pass through
the same 2,400-character chunking boundary as documentation so unusually dense
files remain safe for embedding.

Every `source_summary` chunk links to its source file graph node and fixed-SHA
GitHub URL. Metadata records the source path, file classification, language,
size, blob SHA, source hash, summary hash, structural metrics, exact offsets,
and line ranges. Provenance records the deterministic algorithm and chunker
versions plus the graph edge IDs used to construct the text.

The resumable `summarize_source_files` stage runs after artifact chunking and
prunes stale source-summary documents and their cascading embeddings.

## Infrastructure

Local Docker Compose and GitHub CI use the Trixie-based pgvector PostgreSQL 17
image, matching the base distribution used to initialize local volumes. The
migration enables the `vector` extension before creating vector columns and
leaves the extension installed on downgrade because it may be shared by later
semantic tables.

## Embedding Pipeline

The `embed_semantic_documents` ingestion stage consumes pending or stale
documents in bounded batches and persists content-hash-bound vectors through a
provider-neutral adapter. Re-running the stage does no work for current vectors,
while changed document content is embedded again.

Local development and CI default to `trace-feature-hashing`, a dependency-free,
384-dimensional lexical baseline using deterministic feature hashing over tokens
and adjacent token pairs. It is intentionally a reproducible fallback rather than
a substitute for a neural semantic model. Hosted and neural local providers can
implement the same adapter without changing ingestion or persistence.

The hosted path uses OpenAI `text-embedding-3-small` through the Embeddings API
with an explicit `dimensions=384`, preserving the shared pgvector schema. It is
opt-in with `EMBEDDING_PROVIDER=openai` and requires `OPENAI_API_KEY`. Responses
are restored to provider index order and rejected on missing, duplicate,
non-numeric, or incorrectly sized vectors. Network failures, rate limits, and
server errors use the same bounded provider retry path as hosted enrichment.

## Subsystem Candidate Discovery

The `discover_subsystem_candidates` ingestion stage reads snapshot source and
test files after embeddings are complete. Candidate pairs can be supported by
five deterministic signals:

- exact parent directory;
- import-community membership;
- shared filename tokens;
- co-change relationships from pull requests and commits;
- active-space source-summary embedding similarity.

A pair must have at least two agreeing signals before it contributes to a
cluster. Connected candidate pairs become snapshot-scoped `SUBSYSTEM` nodes with
`knowledge_kind=inferred`, a confidence score, and `status=candidate`. Files link
to candidates through inferred `PART_OF_SUBSYSTEM` edges. Every member also adds
metric evidence targeting the candidate node, including the supporting signals
and membership edge ID.

Candidate identity hashes the sorted member file keys, making retries
idempotent. Rebuilding prunes stale candidates from the same algorithm and relies
on graph foreign keys to remove their obsolete memberships and evidence. The
deterministic name is only a temporary label; an LLM may later name and summarize
the cluster but cannot confirm it without verified evidence.

## Subsystem Enrichment and Verification

The optional `enrich_subsystem_candidates` stage exposes a provider-neutral,
structured naming and summarization boundary. Providers receive only the
candidate's member paths, deterministic signals, and persisted evidence. Their
output must include a bounded name, bounded summary, and persisted evidence IDs.

The deterministic verifier rejects empty, oversized, or foreign citations. It
never allows a model to raise structural confidence. A candidate becomes
`confirmed` only when its pre-model confidence is at least `0.80`, citations
cover at least two distinct member files, and citation coverage reaches 50%.
Otherwise a valid enrichment remains explicitly labeled `candidate`.

Accepted output updates the existing subsystem node and adds separate
`MODEL_INFERENCE` evidence containing provider, model, prompt, verifier, cited
evidence, coverage, and limitations. Existing file-level non-model evidence
remains the basis for confirmation. This verifier establishes citation identity
and coverage; semantic entailment evaluation remains a later quality gate.

The worker can configure an OpenAI Responses API adapter for this boundary. It
requests a strict JSON schema, disables response storage, separates instructions
from untrusted repository evidence, and rejects incomplete, refused, or invalid
structured output. Transient network failures, rate limits, and server errors use
bounded retries; an exhausted transient failure keeps the ingestion job pending
under the provider-neutral worker retry path.

Hosted enrichment is disabled by default, so local development and CI make no
model calls and leave deterministic candidates unchanged. To opt in, set
`OPENAI_API_KEY` and `OPENAI_SUBSYSTEM_ENRICHMENT_ENABLED=true`. The default model
is `gpt-5.6-sol` and can be changed with `OPENAI_SUBSYSTEM_MODEL`.

## Architecture Facts and Subsystem Graph

The `generate_subsystem_graph` stage collapses deterministic file-to-file import
edges across subsystem memberships into directed, derived `DEPENDS_ON` edges.
Each dependency preserves the supporting import-edge IDs and graph-path
evidence. Internal imports are ignored, direction is retained, candidates stay
labeled as candidates, and stale derived edges are pruned on rebuild.

The `generate_architecture_summary` stage persists one snapshot-scoped,
idempotent `ARCHITECTURE_SUMMARY` node. Entry-point candidates are scored from
explicit `package.json` or `pyproject.toml` declarations, Python main guards,
Node executable shebangs, main declarations, and conservative framework filename
conventions. A candidate must reach the configured threshold and is described as
likely rather than observed runtime behavior.

Major external dependencies are ranked by distinct importing files and exclude
standard-library nodes. Only confirmed subsystems become architecture
components. Entry points, dependencies, and confirmed subsystems link back to
the summary through derived edges with source-span, graph-path, or metric
evidence. The summary records central files and explicit limitations and never
claims services, deployment boundaries, or runtime calls from imports alone.

## Software Atlas UX

The repository Software Atlas adds Overview, Architecture, Subsystems,
subsystem-detail, and Timeline routes. The Overview is useful before Ask and
surfaces the generated summary, entry points, confirmed subsystem count,
dependencies, and recent activity. Architecture provides a bounded Cytoscape
graph plus a non-visual dependency list. Subsystem views keep low-confidence
clusters visibly labeled as candidates.

An evidence drawer reads the bounded graph evidence endpoint and shows evidence
type, excerpt, source line range, confidence, and source URL. All inferred or
derived UI elements display confidence labels. Every screen includes loading,
error, empty, partial, and truncated-data messaging where applicable.

## Verification

Integration tests cover idempotent document and vector writes, one-active-space
behavior, pending work, stale-vector filtering, cosine result ordering,
documentation source links, exact offsets, and stale-chunk pruning.
Artifact integration tests also cover title fallbacks, historical graph links,
provider metadata, idempotency, body changes, and removed artifacts.
Source-summary integration tests cover real Python parsing, internal and
external import resolution, graph metrics, fixed-snapshot links, source graph
nodes, source-family filtering, and idempotent writes.
Embedding unit tests cover deterministic vectors, lexical similarity, batch
persistence, invalid provider responses, hosted request dimensions, provider
ordering, retries, and malformed hosted vectors.
Subsystem tests cover multi-signal clustering, cross-directory co-change plus
embedding support, inferred membership persistence, evidence, idempotency, and
stale-candidate pruning.
Enrichment tests cover confirmation thresholds, foreign-citation rejection,
confidence preservation, model-evidence persistence, PostgreSQL candidate reads,
and the no-provider fallback. OpenAI adapter tests cover strict request schemas,
prompt isolation, structured-output parsing, refusals, transient retry behavior,
authentication failures, and opt-in configuration validation without making live
API calls.
Architecture and subsystem-graph tests cover manifest and executable entry-point
signals, standard-library exclusion, directed cross-subsystem imports,
evidence-backed persistence, idempotency, and stale-edge pruning. Graph API tests
cover bounded evidence responses used by the drawer. The frontend production
build, TypeScript compiler, formatter, and linter verify all Atlas routes.

## Next Slice

Week 5 begins decision evidence chains, contributor scoring, hybrid retrieval,
and citation-aware Ask workflows.

```bash
cd backend
uv run alembic upgrade head
uv run alembic check
uv run pytest
```
