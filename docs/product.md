# Trace — Product Requirements

> Functional specification for Trace Software Atlases.

This document defines what Trace must do as a product.

For product vision, read [`overview.md`](overview.md).

For implementation details, use:

- [`ux.md`](ux.md)
- [`architecture.md`](architecture.md)
- [`ontology.md`](ontology.md)
- [`ai-system.md`](ai-system.md)
- [`database.md`](database.md)
- [`api.md`](api.md)
- [`evaluation.md`](evaluation.md)
- [`roadmap.md`](roadmap.md)

---

## 1. Product Summary

Trace transforms a supported public GitHub repository into an interactive **Software Atlas**.

A Software Atlas contains:

- Overview
- Architecture
- Subsystems
- Timeline
- Decisions
- Contributors
- Explore
- Ask

The MVP must help a person with no prior contribution history understand an unfamiliar repository quickly and with visible evidence.

---

## 2. Product Objective

Primary objective:

> Help users build a useful mental model of an unfamiliar repository in approximately ten minutes.

The product must answer:

- What does this repository do?
- How is it structured?
- What are its major subsystems?
- How do subsystems depend on each other?
- Why were major changes introduced?
- How did the project evolve?
- Who has worked most on each subsystem?
- Which files and artifacts support each conclusion?
- What should the user explore next?

---

## 3. Product Scope

## 3.1 MVP Scope

Included:

- public GitHub repositories
- one repository per Atlas
- repository URL submission
- repository validation
- ingestion job creation
- ingestion progress
- metadata ingestion
- source-tree ingestion
- issues
- pull requests
- commits
- releases
- contributors
- discussions when available
- Python source analysis
- TypeScript source analysis
- JavaScript source analysis
- deterministic repository graph
- embeddings
- subsystem discovery
- architecture generation
- decision extraction
- timeline
- contributor expertise
- graph exploration
- evidence-backed AI answers
- evaluation harness
- local Docker Compose setup
- CI

## 3.2 Out of Scope

Excluded from MVP:

- authentication
- user accounts
- private repositories
- GitHub OAuth
- organizations
- billing
- team collaboration
- real-time webhooks
- incremental sync
- multi-repository reasoning
- arbitrary Git providers
- automatic code edits
- IDE extension
- full support for every language
- perfect runtime call graph
- production-scale crawling
- unbounded repository sizes

## 3.3 Future Scope

Potential V2+:

- private repositories
- organization workspaces
- continuous sync
- multi-repository Atlases
- Neo4j graph storage
- repository comparison
- guided learning mode
- impact analysis
- repository health
- IDE integration
- saved queries
- user annotations
- shared Atlases

---

## 4. Supported Repository Profile

Trace MVP is optimized for repositories with:

- public visibility
- valid default branch
- approximately 100–5,000 relevant source files
- approximately 500–5,000 GitHub artifacts
- active issue and pull-request history
- releases
- multiple contributors
- identifiable subsystems
- Python, TypeScript, or JavaScript as primary language

Trace may accept unsupported profiles with reduced analysis.

Reduced-analysis mode must be explicit.

Examples:

- repository too small for subsystem discovery
- unsupported primary language
- no issues or pull requests
- no releases
- shallow contributor history

---

## 5. User Types

## 5.1 New Developer

Goal:

Understand repository structure before making changes.

Needs:

- architecture
- subsystem map
- important files
- entry points
- suggested exploration order

## 5.2 Open-Source Contributor

Goal:

Find where and how to contribute.

Needs:

- relevant subsystem
- related issues
- active contributors
- historical context
- evidence links

## 5.3 Technical Lead

Goal:

Review system decisions and ownership.

Needs:

- architecture
- decision history
- contributor expertise
- dependencies
- timeline

## 5.4 Student

Goal:

Learn from a real repository.

Needs:

- concept-first navigation
- guided exploration
- explanations
- evidence
- learning order

## 5.5 AI Researcher

Goal:

Evaluate graph-augmented software reasoning.

Needs:

- retrieval traces
- confidence
- evidence
- baseline comparison
- evaluation metrics

---

## 6. Product Principles

## 6.1 Evidence Before Inference

Every inferred output must reference supporting repository evidence.

## 6.2 UX Before AI

Users must receive value before entering a prompt.

## 6.3 Deterministic Before Probabilistic

Trace must extract exact relationships before using AI inference.

## 6.4 Uncertainty Must Be Visible

Trace must not present uncertain inference as confirmed fact.

## 6.5 Every Surface Must Answer a User Question

No screen exists only because the underlying data exists.

## 6.6 Progressive Disclosure

Show simple understanding first.

Allow deeper evidence inspection after.

---

## 7. Product States

Each repository Atlas has one primary state.

```text
pending
validating
queued
ingesting
analyzing
generating
ready
partial
failed
```

## 7.1 Pending

Repository record exists.

No work started.

## 7.2 Validating

Trace checks:

- URL
- repository existence
- public visibility
- default branch
- supported limits

## 7.3 Queued

Validation passed.

Job awaits worker.

## 7.4 Ingesting

Trace fetches:

- metadata
- source tree
- artifacts
- contributors

## 7.5 Analyzing

Trace builds:

- ontology entities
- deterministic edges
- dependency graph
- embeddings
- graph metrics

## 7.6 Generating

Trace creates:

- subsystem summaries
- architecture summary
- decisions
- Atlas sections

## 7.7 Ready

Core Atlas is available.

## 7.8 Partial

Some Atlas sections are available.

One or more sections failed or lack evidence.

## 7.9 Failed

Atlas generation cannot continue.

UI must show:

- failed stage
- human-readable reason
- retry option when safe
- preserved completed work when possible

---

## 8. Core User Journey

```text
Landing
    ↓
Paste GitHub URL
    ↓
Validate repository
    ↓
Create repository + job
    ↓
Show progress
    ↓
Generate Atlas
    ↓
Open Overview
    ↓
Explore Architecture / Subsystems / Timeline / Decisions
    ↓
Inspect Evidence
    ↓
Ask Focused Question
```

---

## 9. Feature Priority

| Priority | Meaning |
|---|---|
| P0 | Required for working MVP |
| P1 | Required for complete portfolio MVP |
| P2 | Valuable after core MVP |
| P3 | Future |

---

# 10. Landing Page

**Priority:** P0

## 10.1 Purpose

Let user start Atlas generation immediately.

## 10.2 User Story

> As a user, I want to paste a public GitHub repository URL so Trace can generate a Software Atlas.

## 10.3 Required Elements

- product name
- tagline
- concise explanation
- repository URL input
- Generate Atlas button
- validation feedback
- sample repository links
- current product status
- supported-language notice

## 10.4 Input Rules

Accepted:

```text
https://github.com/{owner}/{repository}
```

May normalize:

```text
https://github.com/{owner}/{repository}/
https://github.com/{owner}/{repository}.git
```

Rejected:

- non-GitHub host
- missing owner
- missing repository
- issue URL
- pull-request URL
- branch URL
- commit URL
- malformed URL

## 10.5 Behavior

On submit:

1. trim input
2. normalize supported URL form
3. validate client-side format
4. call repository creation endpoint
5. show server validation
6. navigate to progress screen

## 10.6 Error States

- invalid URL
- repository not found
- repository private
- repository archived but unsupported by policy
- repository exceeds size limit
- rate limit unavailable
- duplicate repository already indexed
- service unavailable

## 10.7 Acceptance Criteria

- User can submit valid public repository URL.
- Invalid URLs never start ingestion.
- Errors are specific and actionable.
- Existing Atlas redirects to existing repository.
- User sees progress within one navigation.
- No login required.

---

# 11. Atlas Generation Progress

**Priority:** P0

## 11.1 Purpose

Make long-running ingestion understandable.

## 11.2 User Story

> As a user, I want to see what Trace is doing so I know the process is active and where it failed.

## 11.3 Stages

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

## 11.4 Required Information

- current stage
- completed stages
- progress percentage
- start time
- failure state
- retry state
- partial completion notice
- repository name

## 11.5 Acceptance Criteria

- Progress updates without manual refresh.
- Completed stages remain visible.
- Failed stage is clearly identified.
- Retry does not duplicate persisted entities.
- User can leave and return using repository URL.
- Ready state redirects to Overview or exposes Open Atlas button.

---

# 12. Repository Shell

**Priority:** P0

## 12.1 Purpose

Provide consistent Atlas navigation and repository context.

## 12.2 Navigation

```text
Overview
Architecture
Subsystems
Timeline
Decisions
Contributors
Explore
Ask
```

## 12.3 Header

Shows:

- owner/repository
- GitHub link
- primary language
- Atlas status
- last indexed time
- reduced-analysis badge when applicable

## 12.4 Global Actions

- open GitHub
- return home
- refresh current page
- view generation status
- retry failed section when supported

## 12.5 Acceptance Criteria

- Navigation order remains consistent.
- Active section is visible.
- Repository context remains visible.
- Partial Atlas sections are clearly marked.
- Missing sections do not break shell.

---

# 13. Overview

**Priority:** P0

## 13.1 Purpose

Help user understand repository in under one minute.

## 13.2 User Story

> As a new user, I want a concise overview so I know what this project is and where to explore next.

## 13.3 Required Content

### Repository Summary

- repository description
- generated plain-language summary
- primary language
- supported-language status

### Repository Statistics

- stars
- forks
- open issues
- contributors
- release count
- artifact count
- indexed source-file count

### Language Distribution

Chart:

- `react-chartjs-2`
- percentage by language
- source from GitHub language metadata

### Major Subsystems

Each card shows:

- name
- summary
- confidence
- key files
- open subsystem action

### Architecture Summary

- high-level structure
- entry points
- major dependencies
- evidence action

### Recent Releases

- version
- date
- summary
- open timeline action

### Important Decisions

- title
- date
- confidence
- evidence count
- open decision action

### Suggested Exploration Order

Example:

```text
1. Read architecture
2. Explore routing subsystem
3. Inspect dependency injection decision
4. Review recent release timeline
```

## 13.4 Empty States

- no releases
- no inferred subsystems
- no confirmed decisions
- low evidence
- reduced source analysis

## 13.5 Acceptance Criteria

- Overview renders without AI chat.
- Every inferred card exposes confidence.
- Every inferred card links to evidence.
- Missing data uses useful empty state.
- No unsupported claim appears as fact.
- User can reach each major Atlas section from Overview.

---

# 14. Architecture

**Priority:** P1

## 14.1 Purpose

Explain system structure instead of only directory structure.

## 14.2 User Story

> As a developer, I want to see major components and dependencies so I can understand how the system is organized.

## 14.3 Visualization

Use Cytoscape.js.

Node types:

- subsystem
- directory
- file
- external dependency
- entry point

Edge types:

- imports
- depends on
- contains
- inferred dependency

## 14.4 Graph Rules

- deterministic and inferred edges use distinct styling
- graph legend always visible
- low-confidence inferred edges hidden by default or clearly marked
- user can zoom, pan, select, and reset
- graph size capped for readability
- graph expansion is explicit

## 14.5 Selected Node Panel

Shows:

- name
- type
- description
- confidence
- key files
- dependencies
- depended-on-by
- centrality metrics
- related decisions
- related contributors
- evidence
- GitHub links

## 14.6 Controls

- node-type filters
- edge-type filters
- confidence filter
- search
- focus subsystem
- reset layout
- fit graph
- open detail page

## 14.7 Acceptance Criteria

- Graph loads for ready Atlas.
- Selection updates detail panel.
- User can distinguish exact vs inferred relationships.
- Graph does not imply runtime calls from import-only evidence.
- Every inferred dependency exposes evidence.
- Graph remains usable at supported repo size.

---

# 15. Subsystems

**Priority:** P1

## 15.1 Purpose

Let users explore by functional concept.

## 15.2 User Story

> As a user unfamiliar with directory structure, I want repository concepts grouped into subsystems so I can understand functional areas.

## 15.3 Subsystem List

Each item shows:

- name
- summary
- confidence
- file count
- directory count
- related decisions
- top contributors
- activity recency

## 15.4 Subsystem Detail

Required sections:

- summary
- confidence
- discovery evidence
- source directories
- key files
- important symbols
- internal dependencies
- external dependencies
- related issues
- related pull requests
- related decisions
- contributors
- timeline
- suggested next subsystem

## 15.5 Discovery Evidence

Must show signals used:

- directory grouping
- import community
- embedding similarity
- naming patterns
- labels
- documentation references

## 15.6 Low-Confidence Behavior

If confidence below configured threshold:

- mark as candidate subsystem
- avoid definitive language
- show evidence
- allow exploration
- do not place prominently in Overview

## 15.7 Acceptance Criteria

- User can inspect how subsystem was derived.
- Subsystem page links to source files.
- Dependencies distinguish deterministic vs inferred.
- Candidate subsystems are labeled.
- Empty historical data does not hide source structure.

---

# 16. Timeline

**Priority:** P1

## 16.1 Purpose

Explain repository evolution.

## 16.2 User Story

> As a user, I want to see significant events chronologically so I can understand how the project changed.

## 16.3 Event Types

- issue
- pull request
- commit
- release
- decision
- subsystem milestone

## 16.4 Filters

- date range
- event type
- subsystem
- contributor
- release
- confidence for inferred events

## 16.5 Visualizations

Use `react-chartjs-2` for:

- activity over time
- release frequency
- pull-request volume
- contribution trends

Use chronological list for evidence-rich events.

## 16.6 Event Detail

Shows:

- title
- type
- date
- author
- summary
- related entities
- evidence
- GitHub link

## 16.7 Acceptance Criteria

- Events sort chronologically.
- Filters combine predictably.
- Inferred milestones show confidence.
- User can navigate from event to decision, subsystem, contributor, or GitHub.
- No release state uses meaningful fallback.

---

# 17. Decisions

**Priority:** P1

## 17.1 Purpose

Explain why major changes occurred.

## 17.2 User Story

> As a developer, I want evidence-backed decision history so I can understand why the system evolved.

## 17.3 Decision Model

Each confirmed decision includes:

- title
- context
- decision
- alternatives when available
- outcome
- confidence
- supporting evidence
- related issue
- related discussion
- implementing pull request
- commits
- affected files
- affected subsystems
- release

## 17.4 Decision States

```text
candidate
confirmed
insufficient_evidence
rejected
```

Only `confirmed` appears as a normal decision.

`candidate` may appear in a low-confidence section.

`insufficient_evidence` never appears as confirmed history.

## 17.5 Evidence Requirement

Confirmed decision requires:

- at least one source artifact
- evidence span or structured relation
- confidence above threshold
- no contradiction from stronger evidence

## 17.6 Acceptance Criteria

- No evidence means no confirmed decision.
- User can inspect full evidence chain.
- Alternatives only appear when supported.
- Decision confidence is visible.
- User can navigate to GitHub artifacts.
- Trace distinguishes summary from direct evidence.

---

# 18. Contributors

**Priority:** P1

## 18.1 Purpose

Surface repository-backed expertise.

## 18.2 User Story

> As a user, I want to identify contributors associated with a subsystem so I know where knowledge is concentrated.

## 18.3 Contributor List

Shows:

- username
- avatar
- total activity
- active subsystems
- recency
- contribution distribution
- evidence-backed expertise score

## 18.4 Contributor Detail

Shows:

- authored pull requests
- reviewed pull requests when available
- commits
- files modified
- active subsystems
- activity timeline
- recent work
- expertise score breakdown
- GitHub profile link

## 18.5 Expertise Score

Initial explainable model:

```text
expertise_score =
    authored_pr_weight
  + reviewed_pr_weight
  + commit_weight
  + subsystem_file_weight
  + recency_weight
```

Exact weights belong in AI/system documentation.

## 18.6 Language Rules

Allowed:

```text
Repository evidence suggests strong activity in routing.
```

Not allowed:

```text
This person is the routing expert.
```

## 18.7 Acceptance Criteria

- Score breakdown visible.
- Recency affects ranking.
- Contributor identity resolves by GitHub login.
- Bots can be filtered.
- Low-activity repositories show limitations.
- Score never claims absolute expertise.

---

# 19. Explore

**Priority:** P1

## 19.1 Purpose

Allow direct inspection of repository relationships.

## 19.2 User Story

> As a technical user, I want to inspect connected entities so I can verify and discover relationships.

## 19.3 Supported Nodes

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

## 19.4 Supported Actions

- search node
- filter type
- expand neighbors
- limit depth
- inspect edge
- inspect evidence
- focus node
- open GitHub
- navigate to Atlas detail

## 19.5 Graph Controls

- node filters
- edge filters
- provenance filter
- confidence filter
- depth limit
- reset
- fit
- export current selection as JSON later

## 19.6 Acceptance Criteria

- Initial graph is intentionally limited.
- Expansion is user-driven.
- Graph never renders entire large repository by default.
- Evidence panel explains selected edge.
- Inferred relationships are visually distinct.
- Unsupported node details fail gracefully.

---

# 20. Ask

**Priority:** P1

## 20.1 Purpose

Answer focused repository questions using Atlas context.

## 20.2 User Story

> As a user, I want to ask questions after exploration so I can clarify details without manually searching all artifacts.

## 20.3 Supported Question Categories

- overview
- architecture
- subsystem
- decision
- historical
- contributor
- file
- symbol
- semantic search
- mixed

## 20.4 Response Structure

Every response includes:

```json
{
  "answer": "string",
  "confidence": 0.0,
  "evidence": [],
  "citations": [],
  "graph_path": [],
  "related_files": [],
  "related_decisions": [],
  "timeline_events": [],
  "limitations": []
}
```

## 20.5 Insufficient-Evidence Behavior

Trace must not stop at:

```text
No data.
```

Trace should return:

- what could not be confirmed
- nearby evidence
- relevant files
- related artifacts
- possible interpretation labeled as inference
- suggested follow-up question

## 20.6 Query Examples

- How does authentication work?
- Why was Redis introduced?
- Which files define routing?
- What changed in release 1.2?
- Who has worked most on the scheduler?
- Which subsystem should I learn first?
- What evidence supports this architecture edge?

## 20.7 Acceptance Criteria

- Answer always includes citations when evidence exists.
- Unsupported claims are not presented as facts.
- Confidence is visible.
- Retrieval limitations are visible.
- User can open cited source.
- Answer can link back into Atlas surfaces.
- Chat history is session-local in MVP.

---

# 21. Search

**Priority:** P1

Search exists across Atlas.

## 21.1 Searchable Types

- files
- symbols
- issues
- pull requests
- commits
- releases
- contributors
- subsystems
- decisions
- topics

## 21.2 Search Modes

- exact
- prefix
- semantic

## 21.3 Acceptance Criteria

- Results group by type.
- Exact matches rank above semantic matches when relevant.
- Result includes source and confidence when inferred.
- Selecting result opens correct Atlas or GitHub location.

---

# 22. Evidence Panel

**Priority:** P0

## 22.1 Purpose

Provide one consistent evidence interaction across product.

## 22.2 Required Data

- source type
- source title
- source URL
- evidence span
- relationship
- provenance
- confidence
- extraction method
- generated-at timestamp when inferred

## 22.3 Acceptance Criteria

- Evidence UI reused across Atlas surfaces.
- GitHub source opens safely.
- Long evidence collapses.
- Deterministic evidence clearly labeled.
- Inferred evidence clearly labeled.
- Missing source URL handled.

---

# 23. Confidence

**Priority:** P0

## 23.1 Confidence Bands

Suggested UI bands:

```text
high:    >= 0.80
medium:  >= 0.55 and < 0.80
low:     < 0.55
```

Exact thresholds remain configurable.

## 23.2 Display Rules

- high confidence may use direct wording
- medium confidence uses cautious wording
- low confidence must be labeled candidate/inference
- confidence hidden only for deterministic facts

## 23.3 Acceptance Criteria

- Confidence uses same rules across product.
- Numeric value available in detail views.
- Human-readable label available in primary UI.
- Low confidence never styled as confirmed.

---

# 24. Empty States

Every product surface must define useful empty states.

Examples:

## No Releases

```text
This repository has no GitHub releases.
Trace will use commits and pull requests for historical context.
```

## No Confirmed Decisions

```text
Trace could not confirm major decisions from available evidence.
Related pull requests and issues remain available in Timeline and Explore.
```

## No Subsystems

```text
Trace could not derive reliable subsystem boundaries.
Architecture will fall back to directories and import relationships.
```

## No Contributor Review Data

```text
Review activity is unavailable or incomplete.
Contributor ranking uses commits and authored pull requests.
```

---

# 25. Error Handling

## 25.1 User-Facing Error Requirements

Errors must contain:

- what failed
- why when known
- whether data is preserved
- whether retry is available
- next action

## 25.2 Error Categories

- validation
- GitHub API
- rate limit
- ingestion
- parsing
- embedding
- LLM provider
- database
- retrieval
- rendering

## 25.3 Acceptance Criteria

- Internal stack traces never shown.
- Retry is disabled for non-retryable errors.
- Partial Atlas remains accessible when safe.
- Error messages avoid generic “Something went wrong” alone.

---

# 26. Reduced-Analysis Mode

**Priority:** P1

Reduced-analysis mode applies when full Atlas quality is impossible.

Causes:

- unsupported language
- missing history
- repository too small
- repository too large
- parser unavailable
- provider unavailable

UI must show:

- reason
- unavailable sections
- available sections
- expected limitations

---

# 27. Accessibility

**Priority:** P1

Requirements:

- keyboard navigation
- visible focus
- semantic headings
- sufficient contrast
- chart text alternatives
- graph legend
- non-color-only distinction
- screen-reader labels
- reduced-motion support
- responsive layout

Acceptance:

- core navigation works without mouse
- graph relationships have non-visual inspection path
- charts expose summary data

---

# 28. Responsive Behavior

**Priority:** P1

Desktop is primary MVP target.

Tablet supported.

Mobile supports:

- Overview
- Timeline
- Decisions
- Contributors
- Ask

Complex graph views may use reduced mobile mode.

---

# 29. Analytics and Observability

**Priority:** P1

Product events:

- repository submitted
- validation failed
- ingestion started
- ingestion completed
- ingestion failed
- Atlas section opened
- evidence opened
- question asked
- citation opened
- retry triggered

No sensitive repository token data logged.

---

# 30. Product Success Metrics

## 30.1 Primary

User can explain repository architecture and major subsystems within approximately ten minutes.

## 30.2 Secondary

- Atlas completion rate
- ingestion success rate
- time to first useful view
- evidence-open rate
- query citation-open rate
- subsystem usefulness rating
- decision correctness
- user task completion time

## 30.3 Quality Guardrails

- no unsupported certainty
- no hidden partial failures
- no unlabeled inference
- no graph edge without provenance
- no confirmed decision without evidence

---

# 31. Acceptance Test Scenarios

## Scenario A — Valid Repository

Given:

- public supported repository

When:

- user submits URL

Then:

- repository validates
- ingestion starts
- progress appears
- Atlas reaches ready or partial
- Overview opens

## Scenario B — Invalid URL

Given:

- non-GitHub URL

Then:

- no repository created
- validation error shown

## Scenario C — Existing Atlas

Given:

- repository already indexed

Then:

- existing Atlas opens
- duplicate ingestion not created unless refresh explicitly supported

## Scenario D — Missing Decisions

Given:

- no reliable decision evidence

Then:

- Decisions shows empty state
- related issues and PRs remain accessible
- no fabricated decisions appear

## Scenario E — Low-Confidence Subsystem

Given:

- weak cluster evidence

Then:

- subsystem marked candidate
- confidence visible
- not promoted as major subsystem

## Scenario F — Provider Failure

Given:

- LLM provider unavailable

Then:

- deterministic Atlas sections remain available
- AI-derived sections show degraded state
- retry available

## Scenario G — Question With Insufficient Evidence

Then:

- answer states limitation
- nearby evidence returned
- possible interpretation labeled
- no unsupported fact asserted

---

# 32. Release Criteria

MVP product release requires:

- repository submission works
- ingestion progress works
- Overview works
- Architecture works
- Subsystems works
- Timeline works
- Decisions works with evidence rules
- Contributors works with explainable score
- Explore works
- Ask returns cited answers
- partial states work
- evaluation harness exists
- CI passes
- Docker Compose starts full stack
- docs match implementation

---

# 33. Documentation Dependencies

This document intentionally excludes implementation detail.

See:

| Document | Responsibility |
|---|---|
| `overview.md` | Product context |
| `ux.md` | Detailed UI states and layouts |
| `architecture.md` | System components and data flow |
| `ontology.md` | Entity and relationship model |
| `ai-system.md` | Analysis and reasoning pipeline |
| `database.md` | Persistence design |
| `api.md` | HTTP contracts |
| `evaluation.md` | Research methodology |
| `roadmap.md` | Delivery sequence |

---

## Final Product Rule

> Every Trace feature must help a user understand software faster, more accurately, or with stronger evidence. Features that do not improve software understanding do not belong in MVP.
