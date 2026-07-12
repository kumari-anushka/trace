# Trace — Overview

## What Is Trace?

Trace converts a public GitHub repository into an evidence-backed **Software Atlas**.

It helps users answer:

- What does this repository do?
- How is it structured?
- What are its major subsystems?
- Why were important changes introduced?
- How did the project evolve?
- Who has worked most on each subsystem?
- Which files and artifacts support each conclusion?

## Problem

Repository knowledge is fragmented across:

- source code
- issues
- pull requests
- commits
- releases
- discussions
- contributor activity

GitHub stores these artifacts, but users still build the mental model manually.

## Solution

```text
Paste repository URL
    ↓
Generate Atlas
    ↓
Explore architecture, subsystems, decisions, and history
    ↓
Inspect evidence
    ↓
Ask focused questions
```

## Product Output

A Software Atlas contains:

- Overview
- Architecture
- Subsystems
- Timeline
- Decisions
- Contributors
- Explore
- Ask

## Core Principles

1. Evidence before inference.
2. UX before AI.
3. Deterministic before probabilistic.
4. Uncertainty must be visible.
5. Knowledge should persist.
6. Optimize for human understanding.

## Explicit vs Implicit Knowledge

**Explicit**

- files
- imports
- commits
- issues
- pull requests
- releases
- contributors

**Implicit**

- architecture
- subsystems
- decisions
- ownership
- learning order

Trace extracts explicit knowledge deterministically and infers implicit knowledge with confidence and evidence.

## Target Users

- developers entering unfamiliar codebases
- open-source contributors
- technical leads
- students
- AI researchers

## MVP Scope

Included:

- public repositories
- Python, TypeScript, JavaScript
- one repository per Atlas
- graph construction
- embeddings
- subsystem discovery
- decision extraction
- contributor analysis
- cited AI answers

Excluded:

- auth
- private repositories
- billing
- code generation
- IDE integration
- multi-repository reasoning
- Neo4j

## Success

A user with no prior repository knowledge should understand:

- purpose
- architecture
- major subsystems
- major decisions
- evolution
- likely contributor ownership

in approximately ten minutes.

## Documentation Map

| Document | Purpose |
|---|---|
| `product.md` | Features and acceptance criteria |
| `architecture.md` | Services and data flow |
| `ontology.md` | Entities and relationships |
| `ai-system.md` | AI pipeline and retrieval |
| `database.md` | Storage model |
| `api.md` | HTTP contracts |
| `evaluation.md` | Research and quality metrics |
| `ux.md` | Screens and interaction rules |
| `roadmap.md` | Build order |
