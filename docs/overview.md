# Trace — Product Overview

> **Understand any GitHub repository in minutes.**

Trace is an AI Software Intelligence platform that transforms public GitHub repositories into interactive **Software Atlases**.

A Software Atlas is an evidence-backed representation of a software system. It organizes repository knowledge into architecture, subsystems, dependencies, decisions, evolution, contributor expertise, and guided exploration.

Trace is built for people who need to understand a repository before they can safely contribute to it.

---

## 1. Why Trace Exists

Software repositories contain far more knowledge than source code alone.

A mature repository may contain:

- thousands of files
- years of commits
- hundreds of issues
- pull requests containing design discussions
- releases showing product evolution
- contributor activity revealing subsystem ownership
- architectural intent scattered across comments and decisions

GitHub stores these artifacts well, but it does not convert them into a coherent explanation of how the software works.

Developers must reconstruct that explanation manually.

Typical workflow:

```text
Open repository
    ↓
Read README
    ↓
Browse directories
    ↓
Search for relevant files
    ↓
Open issues and pull requests
    ↓
Ask an AI assistant
    ↓
Compare answers with source
    ↓
Build mental model manually
```

This process is slow, repetitive, and dependent on the user's ability to ask the right questions.

Trace changes the workflow:

```text
Paste repository URL
    ↓
Generate Software Atlas
    ↓
Explore architecture, subsystems, decisions, and history
    ↓
Inspect evidence
    ↓
Ask focused questions when needed
```

The product goal is not merely to retrieve repository information.

The goal is to help users build a reliable mental model of unfamiliar software.

---

## 2. Product Definition

Trace is an **AI Software Intelligence platform**.

It converts public GitHub repositories into persistent, explorable knowledge.

### Input

A supported public GitHub repository URL.

Example:

```text
https://github.com/tiangolo/fastapi
```

### Output

A Software Atlas containing:

- repository overview
- architecture map
- subsystem map
- dependency relationships
- decision history
- project evolution timeline
- contributor expertise
- interactive graph exploration
- evidence-backed AI answers

### Product Promise

> A person who has never contributed to a supported repository should be able to understand its main architecture, subsystems, decisions, evolution, and ownership in approximately ten minutes.

---

## 3. What Trace Is Not

Trace is not:

- a code completion tool
- an IDE
- a coding agent
- a pull-request generator
- a generic GitHub chatbot
- a flat vector-search interface
- an automatic replacement for maintainers
- a system that presents inference as fact

Trace may use chat as one interface, but chat is not the product.

The product is the Software Atlas.

---

## 4. Core Concepts

## 4.1 Software Intelligence

Software Intelligence is the process of transforming raw software artifacts into structured, explainable knowledge that helps humans understand software systems.

Raw artifacts include:

- source files
- directories
- imports
- commits
- issues
- pull requests
- discussions
- releases
- contributors
- labels
- metadata

Structured knowledge includes:

- subsystem boundaries
- architectural relationships
- important modules
- design decisions
- historical evolution
- contributor expertise
- learning order

Trace combines deterministic analysis and probabilistic AI to produce this knowledge.

---

## 4.2 Software Atlas

A Software Atlas is an AI-generated, evidence-backed representation of a software system.

It is not only a graph visualization.

It is the complete product output.

A Software Atlas contains:

```text
Repository
├── Overview
├── Architecture
├── Subsystems
├── Timeline
├── Decisions
├── Contributors
├── Explore
└── Ask
```

Each section answers a distinct user question.

| Atlas section | User question |
|---|---|
| Overview | What is this project? |
| Architecture | How is the system structured? |
| Subsystems | What are the major functional areas? |
| Timeline | How did the project evolve? |
| Decisions | Why was a feature or architecture introduced? |
| Contributors | Who appears to know each subsystem best? |
| Explore | How are repository artifacts connected? |
| Ask | What else do I need to understand? |

---

## 4.3 Repository Ontology

Trace does not treat a repository as a collection of unrelated text chunks.

It models the repository using a software-specific ontology.

Core entities include:

- Repository
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
- Subsystem
- Topic
- Decision
- LearningStep

Core relationships include:

- `CONTAINS`
- `IMPORTS`
- `DEPENDS_ON`
- `MODIFIES`
- `REFERENCES`
- `AUTHORED`
- `REVIEWED`
- `RESOLVES`
- `RELEASE_INCLUDES`
- `PART_OF_SUBSYSTEM`
- `ABOUT`
- `DERIVED_FROM`
- `RELATED_TO`
- `RECOMMENDED_BEFORE`

The ontology makes relational questions possible.

Example:

```text
Decision
    └── DERIVED_FROM → Discussion
                           └── REFERENCES → Issue
                                              └── RESOLVED_BY → Pull Request
                                                                      └── INCLUDES → Commit
                                                                                         └── MODIFIES → File
```

This structure enables Trace to explain both what changed and why it changed.

---

## 5. Explicit and Implicit Knowledge

Software repositories contain two kinds of knowledge.

## 5.1 Explicit Knowledge

Explicit knowledge is directly observable.

Examples:

- file paths
- imports
- commit authors
- issue references
- pull-request relationships
- release tags
- modified files
- review activity

These facts are extracted deterministically.

They should be reproducible across repeated ingestion runs.

---

## 5.2 Implicit Knowledge

Implicit knowledge is normally inferred by humans.

Examples:

- subsystem boundaries
- architectural roles
- design decisions
- conceptual topics
- contributor expertise
- recommended learning order

Trace derives this knowledge using:

- graph algorithms
- embeddings
- clustering
- structured language-model extraction
- evidence verification

Implicit knowledge is never presented as equivalent to deterministic fact.

Every inferred output must store:

- confidence
- supporting evidence
- provenance
- generator or model version
- generation timestamp

---

## 6. Product Principles

Trace is governed by six product principles.

## 6.1 Evidence Before Inference

Every AI-generated conclusion must be linked to repository evidence.

When evidence is weak, Trace must show uncertainty.

Trace should not say:

```text
This repository uses Redis because background jobs required retry coordination.
```

unless repository evidence supports that conclusion.

Instead, when evidence is incomplete:

```text
I could not confirm the reason with high confidence.

Related evidence:
- PR #241 introduced Redis
- Issue #219 discusses retry coordination
- worker.py began using Redis in the same release

Possible interpretation:
Redis may have been introduced to support background-job coordination.
```

The interpretation is useful, but clearly labeled.

---

## 6.2 UX Before AI

Users should receive value before typing a prompt.

The Atlas must proactively surface:

- major subsystems
- architecture
- key files
- recent decisions
- contributor ownership
- project history
- suggested learning order

The AI assistant supports exploration.

It does not replace product navigation.

---

## 6.3 Deterministic Before Probabilistic

Trace first extracts what can be known reliably.

Only then does it use AI to infer higher-level meaning.

Example:

```text
GitHub metadata
    ↓
exact artifact relationships
    ↓
source imports
    ↓
dependency graph
    ↓
graph communities
    ↓
LLM naming and explanation
```

This reduces hallucination and improves explainability.

---

## 6.4 Everything Explainable

A user must be able to inspect why Trace produced an output.

Every inferred subsystem, decision, summary, and answer should expose:

- confidence
- evidence
- connected entities
- extraction method where relevant

The UI should make deterministic and inferred relationships visually distinct.

---

## 6.5 Knowledge Persists

A coding assistant often investigates a repository per session.

Trace generates persistent repository knowledge.

Once an Atlas is built, architecture, decisions, timelines, and relationships can be reused across user sessions and queries.

---

## 6.6 Human Understanding First

Trace is not optimized for producing the longest answer.

It is optimized for helping a person understand software.

Outputs should therefore be:

- structured
- concise
- navigable
- visual where useful
- evidence-backed
- progressively disclosed

---

## 7. Target Users

Trace is for anyone who has not contributed to a repository but needs to understand it.

## 7.1 Developer Entering an Unfamiliar Codebase

Primary needs:

- fast mental model
- architecture overview
- subsystem boundaries
- key files
- suggested starting point

Success:

The developer can explain the system at a high level and identify where to investigate next.

---

## 7.2 Open-Source Contributor

Primary needs:

- contribution entry points
- relevant subsystem
- related issues
- maintainers or active contributors
- historical context

Success:

The contributor can identify where a change belongs and who has relevant context.

---

## 7.3 Technical Lead or Reviewer

Primary needs:

- architecture
- decision history
- ownership
- dependency relationships
- subsystem evolution

Success:

The lead can inspect repository context without manually reconstructing history.

---

## 7.4 Student or Learner

Primary needs:

- guided exploration
- conceptual grouping
- learning order
- examples tied to real code
- evidence-backed explanations

Success:

The learner understands how a real-world project is structured rather than only reading isolated tutorials.

---

## 7.5 AI Engineer or Researcher

Primary needs:

- inspectable graph construction
- retrieval traces
- confidence
- reproducible experiments
- baseline comparisons
- evaluation metrics

Success:

The researcher can study how graph-augmented reasoning performs on software-understanding tasks.

---

## 8. User Journey

## 8.1 Submit Repository

User opens Trace and pastes a public GitHub repository URL.

```text
https://github.com/owner/repository
```

Trace validates:

- host
- owner
- repository name
- public visibility
- repository availability
- supported size
- supported source profile

---

## 8.2 Generate Atlas

Trace creates an ingestion job and shows progress.

Expected stages:

```text
Validating repository
Fetching repository metadata
Fetching source tree
Fetching issues
Fetching pull requests
Fetching commits
Fetching releases
Fetching contributors
Normalizing artifacts
Building structural graph
Analyzing dependencies
Generating embeddings
Discovering subsystems
Extracting decisions
Generating Atlas
Ready
```

The user should always know:

- current stage
- progress
- failure reason
- whether retry is possible

---

## 8.3 Explore Atlas

After generation, the user enters the repository Overview.

Suggested flow:

```text
Overview
    ↓
Architecture
    ↓
Subsystem
    ↓
Decision or Timeline
    ↓
Evidence
    ↓
Ask focused question
```

The user is not forced into chat.

---

## 8.4 Inspect Evidence

Any inferred output can be inspected.

Example:

```text
Subsystem: Authentication
Confidence: 0.84

Evidence:
- backend/auth/
- auth_service.py
- 17 files in import cluster
- label: authentication
- PR #218
- Issue #197
```

The user can follow evidence back to GitHub.

---

## 8.5 Ask AI

The user may ask:

- How does request routing work?
- Why was dependency injection introduced?
- Which files define authentication?
- What changed in release 0.100?
- Who has worked most on the scheduler?
- What should I understand before modifying this module?

Trace retrieves from the Atlas, expands connected evidence, and returns a cited answer.

---

## 9. Software Atlas Surfaces

## 9.1 Overview

Purpose:

Help the user understand the project in under one minute.

Contains:

- repository description
- generated summary
- languages
- primary frameworks
- repository statistics
- major subsystems
- architecture summary
- recent releases
- important decisions
- suggested exploration order

---

## 9.2 Architecture

Purpose:

Explain system structure rather than only directory structure.

Contains:

- subsystem nodes
- dependency edges
- key entry points
- central modules
- external dependencies
- selected-node detail panel
- evidence

Visualization:

- Cytoscape.js for node-edge architecture maps
- deterministic and inferred edges visually distinct

---

## 9.3 Subsystems

Purpose:

Allow exploration by functional concepts.

Each subsystem contains:

- name
- summary
- confidence
- source directories
- files
- important symbols
- internal dependencies
- external dependencies
- related issues
- related pull requests
- related decisions
- contributors
- timeline
- evidence

---

## 9.4 Timeline

Purpose:

Explain repository evolution.

Contains:

- issues
- pull requests
- commits
- releases
- decisions
- subsystem milestones

Visualization:

- `react-chartjs-2` for activity trends
- chronological event list for evidence
- filters by date, artifact type, and subsystem

---

## 9.5 Decisions

Purpose:

Explain why software changed.

Each decision contains:

- title
- context
- decision
- alternatives when available
- outcome
- confidence
- evidence chain
- related issue
- related discussion
- implementing pull request
- commits
- affected files
- affected subsystems
- release

No evidence means no confirmed decision.

---

## 9.6 Contributors

Purpose:

Surface evidence-backed contributor expertise.

Each contributor profile contains:

- contribution summary
- authored pull requests
- reviewed pull requests when available
- commits
- modified files
- active subsystems
- recency
- contribution timeline
- explainable expertise score

Trace should say:

```text
Repository evidence suggests this contributor has strong activity in authentication.
```

It should not claim absolute expertise.

---

## 9.7 Explore

Purpose:

Allow direct graph exploration.

Capabilities:

- search entities
- filter node types
- expand neighbors
- inspect relationships
- inspect evidence
- open GitHub artifacts
- focus on a subsystem or decision

---

## 9.8 Ask

Purpose:

Answer questions that the generated Atlas does not fully address through navigation.

Every answer includes:

- direct answer
- confidence
- citations
- evidence summary
- graph path
- related files
- related decisions
- timeline context when relevant

---

## 10. Differentiation

## 10.1 GitHub

GitHub stores and exposes repository artifacts.

Trace organizes those artifacts into understanding.

---

## 10.2 GitHub Search

GitHub Search finds matching text.

Trace follows relationships and synthesizes context.

---

## 10.3 Claude Code and Cursor

Coding agents help users:

- inspect code
- modify code
- generate code
- run commands
- fix issues

Trace helps users:

- understand the system before changing it
- navigate persistent repository knowledge
- inspect architecture visually
- connect current code to historical decisions
- explore without knowing what questions to ask

Trace is not better at coding.

It solves a different job.

---

## 10.4 Generic RAG Applications

Generic RAG applications often:

- chunk documents
- embed text
- retrieve similar chunks
- generate an answer

Trace adds software-specific structure:

- ontology
- deterministic graph
- dependency analysis
- graph algorithms
- subsystem discovery
- decision extraction
- adaptive retrieval
- evidence verification

The graph is not decorative.

It is part of reasoning.

---

## 11. MVP Scope

## 11.1 Included

- public GitHub repositories
- one repository per Atlas
- Python source analysis
- TypeScript source analysis
- JavaScript source analysis
- repository metadata
- source tree
- issues
- pull requests
- commits
- releases
- contributors
- discussions when available
- deterministic graph construction
- source import analysis
- embeddings
- subsystem discovery
- decision extraction
- architecture view
- timeline
- contributor explorer
- graph exploration
- evidence-backed question answering
- evaluation harness
- Docker Compose
- CI

---

## 11.2 Excluded

- authentication
- user accounts
- private repositories
- GitHub OAuth
- organizations
- billing
- team workspaces
- real-time webhooks
- multi-repository reasoning
- IDE extension
- automatic code modification
- support for arbitrary Git providers
- perfect runtime call-graph analysis
- full AST support for every programming language
- production-scale crawling

---

## 11.3 Future Scope

- private repositories
- organization workspaces
- incremental synchronization
- multi-repository Atlases
- Neo4j graph storage
- repository comparison
- guided learning mode
- impact analysis
- repository health intelligence
- IDE integration

MVP uses PostgreSQL for graph storage.

A graph repository abstraction should allow a later Neo4j implementation.

---

## 12. Supported Repository Profile

Trace MVP is optimized for repositories with:

- public visibility
- default branch
- approximately 100–5,000 relevant source files
- approximately 500–5,000 GitHub artifacts
- active issue and pull-request history
- releases
- multiple contributors
- identifiable subsystems
- Python, TypeScript, or JavaScript as primary language

Other languages may be accepted with reduced structural analysis.

Repositories outside supported limits should receive a clear error or reduced-analysis notice.

---

## 13. Success Metrics

## 13.1 Product Success

A user unfamiliar with a supported repository can correctly explain:

- repository purpose
- high-level architecture
- major subsystems
- important dependencies
- major decisions
- project evolution
- contributor ownership

within approximately ten minutes.

---

## 13.2 AI Quality

The system should measure:

- faithfulness
- answer relevance
- context precision
- context recall
- citation correctness
- evidence coverage
- graph-edge precision
- subsystem quality
- latency
- token cost

---

## 13.3 UX Success

The interface should enable useful exploration before the user asks a question.

Indicators:

- users open Atlas sections without prompting
- users can reach source evidence in few interactions
- users understand uncertainty
- users can identify next exploration step
- users do not need to understand graph terminology

---

## 13.4 Engineering Success

The system should support:

- idempotent ingestion
- resumable jobs
- typed APIs
- database migrations
- structured logs
- provider abstractions
- testable graph construction
- CI
- reproducible local startup

---

## 13.5 Portfolio Success

Trace should demonstrate:

- product thinking
- UX design
- backend engineering
- frontend visualization
- knowledge representation
- graph algorithms
- embeddings
- retrieval
- LLM orchestration
- explainability
- evaluation
- testing
- infrastructure

---

## 14. Research Direction

Primary research question:

> Does an adaptive graph-augmented Software Atlas improve repository-understanding tasks compared with vector-only retrieval?

Planned comparison:

```text
Keyword / metadata retrieval
vs.
Vector-only RAG
vs.
Graph-augmented retrieval
vs.
Adaptive hybrid retrieval
```

Evaluation tasks:

- architecture understanding
- subsystem identification
- decision traceability
- historical evolution
- contributor expertise
- semantic repository search

A hand-labeled QA set will include:

- question
- expected answer
- gold evidence
- query category

A small user study will compare:

```text
GitHub + README
vs.
Trace Software Atlas
```

Measured outcomes:

- completion time
- correctness
- evidence quality
- perceived understanding

---

## 15. Documentation Map

This document explains the product at a high level.

Detailed documentation lives in:

| Document | Purpose |
|---|---|
| `product.md` | Functional requirements and acceptance criteria |
| `ux.md` | Screens, navigation, states, and interaction design |
| `architecture.md` | Services, components, data flow, and deployment |
| `ontology.md` | Repository entities, relationships, and inference rules |
| `ai-system.md` | Ingestion, analysis, retrieval, reasoning, and verification |
| `database.md` | Tables, constraints, indexes, and migrations |
| `api.md` | REST endpoints, payloads, validation, and errors |
| `evaluation.md` | Baselines, datasets, metrics, and experiments |
| `roadmap.md` | Build phases, milestones, and delivery order |

---

## Final Definition

> Trace is an AI Software Intelligence platform that transforms public GitHub repositories into interactive Software Atlases. It combines deterministic repository analysis, software-specific ontologies, graph algorithms, semantic retrieval, and evidence-backed AI reasoning to help people understand software architecture, decisions, evolution, and ownership in minutes.
