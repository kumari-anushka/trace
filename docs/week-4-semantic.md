# Week 4 — Semantic Persistence

Week 4 starts with the storage and retrieval boundary required by chunking,
embeddings, subsystem discovery, and later hybrid retrieval.

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

## Next Slice

Add a provider-neutral embedding adapter that consumes pending documents,
persists content-hash-bound vectors, and supports reproducible local testing.

## Verification

Integration tests cover idempotent document and vector writes, one-active-space
behavior, pending work, stale-vector filtering, cosine result ordering,
documentation source links, exact offsets, and stale-chunk pruning.
Artifact integration tests also cover title fallbacks, historical graph links,
provider metadata, idempotency, body changes, and removed artifacts.
Source-summary integration tests cover real Python parsing, internal and
external import resolution, graph metrics, fixed-snapshot links, source graph
nodes, source-family filtering, and idempotent writes.

```bash
cd backend
uv run alembic upgrade head
uv run alembic check
uv run pytest
```
