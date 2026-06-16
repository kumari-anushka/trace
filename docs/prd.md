# Product Requirements Document — Trace

**Working title:** Trace — GitHub-grounded Organizational Memory
**Tagline:** *Trace any decision back to its evidence.*
**Version:** 1.0 (rescoped MVP)
**Owner:** Anushka
**Status:** Draft for build
**Context:** MCA capstone / portfolio project (project 1 of 2). Built solo. Goal is a credible, evaluable AI system that demonstrates a knowledge-graph + LLM reasoning architecture end to end — not a multi-tenant SaaS at scale.
**Portfolio fit:** Trace demonstrates AI *system orchestration* — retrieval, graph reasoning, LLM workflows, and evaluation. Its companion project, **Slate**, demonstrates *modeling* (training and evaluating a ranking model). Together they show range across orchestration and ML.

---

## 1. Problem & vision

Engineering knowledge — *why* a feature exists, *which* PR implemented a requirement, *who* understands a subsystem — is scattered across issues, PRs, commits, releases and discussions, and decays as people and context move on. Flat keyword/RAG search retrieves documents but cannot answer relational, "why" and "how-did-this-evolve" questions because it loses the connections between artifacts.

Trace turns a software project's GitHub history into a **living knowledge graph** and answers questions with **evidence-backed reasoning** that traces real relationships across issues, PRs, commits and releases.

The differentiator vs. plain RAG: relationships are not guessed. They are extracted **deterministically** from GitHub metadata (high precision, real citations), with an LLM **semantic overlay** on top for topics, summaries and "why" reasoning.

---

## 2. Goals and non-goals

### Goals
- Ingest a real OSS repository's full history (issues, PRs, commits, releases, discussions) into a structured knowledge graph.
- Build the structural graph **deterministically** from API metadata; use the LLM only for the semantic layer.
- Answer three flagship question types with citations: **decision traceability**, **semantic + graph search**, **expert discovery**.
- Provide an interactive **D3 graph view** and a **timeline view**.
- Ship a **real evaluation harness** measuring answer quality against a hand-labeled QA set, comparing baseline RAG vs. graph-augmented retrieval.
- Run fully via `docker compose up`, with one CI workflow (lint, test, build).

### Non-goals (explicitly out of scope for v1.0)
- Multi-source ingestion (Google Docs, meeting notes, PDFs) — *future work*.
- Multiple databases. **One** datastore: PostgreSQL + pgvector. No Neo4j, no Qdrant in v1.0.
- Production deployment, multi-tenancy, auth/SSO, horizontal scaling.
- Real-time / streaming ingestion. Ingestion is batch / on-demand.
- "SaaS polish" (billing, onboarding, org management).

---

## 3. Target users & personas

| Persona | Need | Primary feature |
|---|---|---|
| New engineer onboarding | "Why does this module exist? What decisions shaped it?" | Decision traceability |
| Tech lead / reviewer | "What discusses authentication? What's the history here?" | Semantic + graph search, timeline |
| Eng manager | "Who knows the payments subsystem best?" | Expert discovery |

For v1.0 the "organization" is a single open-source repository chosen as the demo corpus (a mature project with rich issue/PR/discussion history). This sidesteps OAuth/permissions and proprietary-data issues while keeping the data realistic.

---

## 4. Corpus & data sources (v1.0)

- **Source:** GitHub REST + GraphQL API for one configured repository.
- **Artifacts ingested:** issues, pull requests, commits, files touched per commit, releases, discussions, comments, labels, milestones, and user/author/reviewer metadata.
- **Target corpus size:** a repo with roughly 1,000–3,000 issues+PRs (large enough to be non-trivial, small enough to build/evaluate solo).
- **Auth:** a single GitHub personal access token (read-only) supplied via env var.

---

## 5. System architecture

```
                ┌────────────────────────────────────────────┐
                │  React + TypeScript (Vite) frontend          │
                │  • Chat/QA  • D3 graph view  • Timeline view │
                └───────────────────────┬──────────────────────┘
                                        │ REST/JSON
                ┌───────────────────────▼──────────────────────┐
                │  FastAPI backend                              │
                │  ┌─────────────┐  ┌──────────────┐            │
                │  │ Ingestion   │  │ Reasoning     │            │
                │  │ + Graph     │  │ (LangGraph)   │            │
                │  │ builder     │  │ hybrid retr.  │            │
                │  └──────┬──────┘  └──────┬────────┘            │
                └─────────┼────────────────┼─────────────────────┘
                          │                │
                ┌─────────▼────────────────▼─────────┐
                │  PostgreSQL + pgvector              │
                │  nodes | edges | embeddings | docs  │
                └─────────────────────────────────────┘
   External: GitHub API (ingest)  •  LLM + embedding API (extraction, QA)
```

**Why single Postgres:** `nodes` + `edges` tables with recursive CTEs cover all graph traversal needed at this corpus size; `pgvector` covers semantic retrieval. Three databases would add operational surface area without adding capability at this scale.

---

## 6. Data model

### 6.1 Node types
- `Person` (GitHub user: author, committer, reviewer)
- `Issue`
- `PullRequest`
- `Commit`
- `File` (path / module)
- `Release`
- `Discussion`
- `Label`
- `Topic` — *LLM-derived* semantic cluster (e.g. "authentication", "rate limiting")
- `Decision` — *LLM-derived* synthesized decision node (the traceability backbone)

### 6.2 Edge types

| Edge | Source → Target | Provenance |
|---|---|---|
| `AUTHORED` | Person → Issue/PR/Commit/Discussion | Deterministic |
| `REVIEWED` | Person → PR | Deterministic |
| `RESOLVES` | PR → Issue (parsed from "closes/fixes #N") | Deterministic |
| `CONTAINS` | PR → Commit | Deterministic |
| `MODIFIES` | Commit → File | Deterministic |
| `INCLUDES` | Release → PR | Deterministic |
| `REFERENCES` | Issue/PR → Issue/PR (cross-refs) | Deterministic |
| `LABELED` | Issue/PR → Label | Deterministic |
| `ABOUT` | Artifact → Topic | LLM-derived (confidence) |
| `DERIVED_FROM` | Decision → Issue/PR/Discussion | LLM-derived (confidence) |

Every edge stores `provenance ∈ {deterministic, llm}` and, for LLM edges, a `confidence` score and the source span(s) used. **Deterministic edges are treated as ground-truth citations; LLM edges are always shown with their evidence and confidence.** This split is the core integrity guarantee of the system.

### 6.3 Tables (indicative)
- `nodes(id, type, github_id, title, body, metadata jsonb, created_at, updated_at)`
- `edges(id, type, src_id, dst_id, provenance, confidence, evidence jsonb)`
- `embeddings(node_id, chunk_id, chunk_text, vector vector(N))`
- `documents(node_id, raw_payload jsonb)` — raw API payloads for re-processing.

---

## 7. Functional requirements

### 7.1 Ingestion (F1)
- F1.1 Pull full history for the configured repo via GitHub API, with pagination and rate-limit handling (backoff + resume).
- F1.2 Persist raw payloads, then normalize into `nodes`.
- F1.3 Re-ingestion is idempotent (upsert by `github_id`).

### 7.2 Deterministic graph construction (F2)
- F2.1 Build all deterministic edges (table in §6.2) from metadata and body parsing ("closes #N", `@mentions`, cross-references).
- F2.2 Entity resolution for `Person` across login/name variants.
- F2.3 Deterministic edges must have **100% precision** (they are read directly from the API; any parse must be exact-match on the documented GitHub closing-keyword grammar).

### 7.3 Semantic overlay (F3)
- F3.1 Chunk + embed artifact text into `embeddings` (pgvector).
- F3.2 LLM extracts `Topic` nodes and `ABOUT` edges, with confidence and source spans.
- F3.3 LLM synthesizes `Decision` nodes from clusters of related issues/PRs/discussions and links them via `DERIVED_FROM`.

### 7.4 Hybrid retrieval (F4)
- F4.1 Vector search over `embeddings` for semantic recall.
- F4.2 Graph traversal (recursive CTE) to expand from seed nodes along relevant edges.
- F4.3 A query router picks vector-first, graph-first, or both, by query type. Rationale: current best practice is hybrid systems that route each query to the appropriate backend rather than relying on a single retrieval mode.

### 7.5 Reasoning & QA (F5) — LangGraph
- F5.1 LangGraph workflow: classify query → retrieve (hybrid) → assemble evidence subgraph → generate answer → attach citations.
- F5.2 Every answer returns **citations** linking back to specific nodes/edges (clickable to the artifact).
- F5.3 Answers must not assert relationships absent from the graph; LLM-derived links are flagged as such.

### 7.6 Flagship queries (F6)
- **Decision traceability:** "Why was X built?" → walks `Decision —DERIVED_FROM→ Issue/PR/Discussion` and `PR —RESOLVES→ Issue`, returns the evidence chain.
- **Semantic + graph search:** "What discusses authentication?" → vector recall + `ABOUT` topic expansion, ranked.
- **Expert discovery:** "Who knows subsystem Y?" → aggregate `AUTHORED`/`REVIEWED`/`MODIFIES` over artifacts linked to the topic/files, ranked by contribution recency and volume.

### 7.7 Visualization (F7)
- F7.1 **Graph view (D3):** force-directed graph of the evidence subgraph for a given answer or entity; node types color-coded; deterministic vs. LLM edges visually distinguished; click a node to inspect/expand.
- F7.2 **Timeline view:** chronological view of how a feature/decision/project evolved (issues → PRs → releases on a time axis), filterable by topic.
- F7.3 Visualizations are driven by the same graph the answers cite — UI and reasoning share one source of truth.

---

## 8. Evaluation & quality (F8) — the credibility layer

- F8.1 **Hand-labeled QA set:** 30–50 question/answer pairs over the corpus, spanning all three flagship query types, with gold evidence references.
- F8.2 **Metrics (RAGAS):** faithfulness, answer relevancy, context precision, context recall.
- F8.3 **Comparison:** baseline vector-only RAG vs. graph-augmented retrieval, reported as a table — this is the central experimental result for the report.
- F8.4 **Graph integrity check:** sample LLM-derived edges and report precision against manual review; report deterministic-edge coverage.

---

## 9. Technical stack

| Layer | Choice |
|---|---|
| Frontend | React + TypeScript + Vite; D3.js (graph + timeline); TanStack Query for data fetching |
| Backend | FastAPI (Python 3.11+); LangGraph for reasoning workflow |
| Datastore | PostgreSQL 16 + pgvector (single service) |
| Embeddings | Configurable (e.g. `text-embedding-3-small` or a local model) |
| LLM | Configurable provider (Claude / GPT) for extraction + generation |
| Eval | RAGAS |
| Infra | Docker Compose (frontend, backend, postgres); GitHub Actions: lint + test + build |
| Testing | pytest (backend), vitest + React Testing Library (frontend) |

---

## 10. Non-functional requirements

- **Ingestion:** full ingest of a ~2,000-artifact repo completes in under ~30 minutes (rate-limit bound).
- **Query latency:** p50 < 5 s, p95 < 12 s (LLM-generation bound).
- **Determinism:** deterministic edges reproducible 1:1 on re-ingest.
- **Run:** `docker compose up` brings up the full stack locally; seeded demo corpus available.
- **Observability:** structured logs for ingestion progress, retrieval traces, and token usage per query.

---

## 11. Milestones (suggested phasing)

| Phase | Deliverable | Done when |
|---|---|---|
| P0 — Skeleton | Repo, Docker Compose, Postgres+pgvector, FastAPI + React hello-world, CI green | `docker compose up` serves an empty app; CI passes |
| P1 — Ingestion | GitHub ingest → `nodes` + raw payloads, idempotent | One repo fully ingested and queryable in DB |
| P2 — Deterministic graph | All §6.2 deterministic edges + Person resolution | Edges built; spot-check shows correct PR↔issue links |
| P3 — Semantic overlay | Embeddings, Topic/ABOUT, Decision/DERIVED_FROM | Vector search + topic/decision nodes populated |
| P4 — Retrieval + QA | LangGraph hybrid pipeline with citations | All three flagship queries answer with evidence |
| P5 — Frontend | D3 graph view + timeline + QA UI | Answers render with clickable evidence subgraph |
| P6 — Evaluation | QA set + RAGAS + baseline-vs-graph comparison table | Metrics reported; integrity check done |
| P7 — Polish | Tests, docs, demo script, README, report | Reproducible from clean clone; report-ready |

---

## 12. Risks & mitigations

| Risk | Mitigation |
|---|---|
| LLM-extracted graph is noisy | Make the structural graph deterministic; isolate LLM to a clearly-flagged overlay with confidence + evidence |
| Scope creep back toward the original spec | Non-goals in §2 are binding for v1.0; new sources/DBs go to §13 |
| GitHub rate limits stall ingestion | Backoff + resumable, idempotent ingest; cache raw payloads |
| LLM cost/latency | Cache extractions; batch; configurable smaller models; pgvector pre-filtering before LLM |
| Evaluation underdone (most common failure) | QA set + RAGAS scoped as a first-class phase (P6), not an afterthought |

---

## 13. Future work (deferred, not abandoned)

- Multi-source ingestion: Google Docs, meeting notes, PDFs, markdown wikis.
- Dedicated graph DB (Neo4j) and/or vector DB (Qdrant) if corpus scale demands it.
- Incremental/streaming ingestion and webhooks.
- Multi-repo / true multi-tenant "organization" model, auth, deployment.
- Lighter-weight graph-RAG variants (e.g. LightRAG-style dual-level retrieval) as a comparison arm.

---

## 14. Success metrics

- All three flagship query types return correct, citation-backed answers on the demo corpus.
- Graph-augmented retrieval beats baseline vector RAG on the RAGAS table (esp. faithfulness and context recall).
- 100% precision on deterministic edges; reported precision on a sample of LLM edges.
- Full stack reproducible from a clean clone via `docker compose up`; CI green.

## 15. Repo Structure
```
trace/
├── README.md
├── docker-compose.yml
├── .env.example
├── .github/workflows/ci.yml
├── backend/
│   ├── pyproject.toml            # or requirements.txt
│   ├── Dockerfile
│   ├── alembic/                  # DB migrations
│   ├── app/
│   │   ├── main.py               # FastAPI entry
│   │   ├── config.py
│   │   ├── db/
│   │   │   ├── session.py
│   │   │   └── models.py         # nodes, edges, embeddings, documents
│   │   ├── ingestion/
│   │   │   ├── github_client.py  # paginated, rate-limit aware
│   │   │   ├── fetchers.py       # issues / PRs / commits / releases / discussions
│   │   │   └── normalize.py
│   │   ├── graph/
│   │   │   ├── deterministic.py  # RESOLVES, CONTAINS, MODIFIES, … from metadata
│   │   │   ├── entity_resolution.py
│   │   │   └── traversal.py      # recursive-CTE graph queries
│   │   ├── semantic/
│   │   │   ├── embeddings.py     # chunk + embed → pgvector
│   │   │   ├── topics.py         # LLM topic extraction (ABOUT edges)
│   │   │   └── decisions.py      # LLM decision synthesis (DERIVED_FROM)
│   │   ├── retrieval/
│   │   │   ├── vector.py
│   │   │   ├── hybrid.py
│   │   │   └── router.py         # vector / graph / both
│   │   ├── reasoning/
│   │   │   ├── graph_workflow.py # LangGraph pipeline
│   │   │   └── citations.py
│   │   ├── api/
│   │   │   ├── routes_query.py
│   │   │   ├── routes_graph.py
│   │   │   └── routes_ingest.py
│   │   └── schemas/              # pydantic models
│   ├── scripts/ingest.py         # CLI: ingest a repo
│   └── tests/
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── Dockerfile
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── api/                  # typed API client
│       ├── components/
│       │   ├── QueryPanel.tsx
│       │   ├── GraphView.tsx     # D3 force-directed
│       │   ├── TimelineView.tsx  # D3 timeline
│       │   └── EvidencePanel.tsx # cited answer + sources
│       ├── hooks/
│       ├── types/
│       └── styles/
├── eval/
│   ├── qa_set.jsonl              # hand-labeled QA pairs + gold evidence
│   ├── run_eval.py               # RAGAS, baseline vs graph
│   └── results/
└── docs/PRD_Trace.md
```