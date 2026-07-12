# Trace — UX Specification

> User experience, information architecture, screen behavior, interaction rules, visual hierarchy, accessibility, and responsive design for Trace.

This document defines how users interact with Trace.

Related documents:

- [`overview.md`](overview.md) — product context
- [`product.md`](product.md) — functional requirements
- [`architecture.md`](architecture.md) — technical architecture
- [`ontology.md`](ontology.md) — entity and relationship semantics
- [`ai-system.md`](ai-system.md) — AI behavior and confidence
- [`api.md`](api.md) — backend contracts
- [`roadmap.md`](roadmap.md) — implementation sequence

---

## 1. UX Goal

Trace must help users build a useful mental model of an unfamiliar repository quickly.

Primary UX goal:

> A user should understand repository purpose, architecture, major subsystems, key decisions, evolution, and likely ownership in approximately ten minutes.

The interface must reduce:

- uncertainty
- unnecessary navigation
- raw data overload
- dependence on chat
- hidden AI reasoning
- unsupported certainty

---

## 2. UX Principles

## 2.1 Understand Before Explore

Default views show synthesized understanding first.

Raw graph and artifact exploration come later.

## 2.2 Visual Before Conversational

Users should gain value before asking a question.

Primary order:

```text
Overview
→ Architecture
→ Subsystems
→ Timeline / Decisions
→ Explore
→ Ask
```

## 2.3 Evidence Always Reachable

Every inferred output must provide:

- confidence
- evidence action
- source links
- provenance where relevant

Evidence should be one interaction away.

## 2.4 Uncertainty Must Be Visible

Trace must distinguish:

```text
deterministic
derived
inferred
candidate
unavailable
```

Do not use vague wording alone.

## 2.5 Progressive Disclosure

Show concise summaries first.

Reveal:

- metrics
- graph paths
- raw artifacts
- extraction details
- full evidence

only when requested.

## 2.6 Dense, Not Cluttered

Trace targets technical users.

Information density may be high.

Hierarchy must remain strong.

## 2.7 Consistent Mental Model

Same entity must appear consistently across:

- Architecture
- Subsystems
- Timeline
- Decisions
- Contributors
- Explore
- Ask

---

## 3. Product Personality

Visual direction:

```text
Linear-like
technical
calm
precise
modern
high-density
evidence-first
```

Avoid:

- playful mascots
- large marketing gradients inside app
- excessive rounded cards
- chat-first layouts
- decorative graphs
- vague AI sparkle language

---

## 4. Information Architecture

```text
Home
└── Repository Atlas
    ├── Overview
    ├── Architecture
    ├── Subsystems
    ├── Timeline
    ├── Decisions
    ├── Contributors
    ├── Explore
    └── Ask
```

Secondary surfaces:

```text
Repository status
Evidence drawer
Entity detail panel
Search overlay
Error/retry panel
```

---

## 5. Global Navigation

## 5.1 Desktop Layout

```text
┌───────────────────────────────────────────────┐
│ Top Bar                                       │
├───────────────┬───────────────────────────────┤
│ Sidebar       │ Main Content                  │
│               │                               │
│ Overview      │                               │
│ Architecture  │                               │
│ Subsystems    │                               │
│ Timeline      │                               │
│ Decisions     │                               │
│ Contributors  │                               │
│ Explore       │                               │
│ Ask           │                               │
└───────────────┴───────────────────────────────┘
```

## 5.2 Sidebar

Shows:

- Trace logo
- repository owner/name
- repository status
- Atlas navigation
- GitHub link
- generation status action

## 5.3 Top Bar

Shows:

- page title
- repository context
- global search
- last indexed time
- reduced-analysis badge
- page actions

## 5.4 Mobile Navigation

Use:

- compact top bar
- drawer navigation
- bottom actions only where useful

Complex graph pages may use limited mobile mode.

---

## 6. Navigation Rules

- active page clearly highlighted
- navigation order never changes
- unavailable pages remain visible with status
- partial pages show warning badge
- browser back/forward works
- deep links supported
- repository context persists
- switching page preserves reasonable filters when returning

---

## 7. Route Structure

```text
/
```

Landing page.

```text
/repositories/:repositoryId/status
```

Generation progress.

```text
/repositories/:repositoryId/overview
/repositories/:repositoryId/architecture
/repositories/:repositoryId/subsystems
/repositories/:repositoryId/subsystems/:subsystemId
/repositories/:repositoryId/timeline
/repositories/:repositoryId/decisions
/repositories/:repositoryId/decisions/:decisionId
/repositories/:repositoryId/contributors
/repositories/:repositoryId/contributors/:contributorId
/repositories/:repositoryId/explore
/repositories/:repositoryId/ask
```

---

## 8. Global UI States

Every page must define:

```text
loading
ready
partial
empty
error
unavailable
```

## 8.1 Loading

Use skeletons.

Do not use full-page spinner unless first app boot.

## 8.2 Ready

Render complete content.

## 8.3 Partial

Render available content.

Show limitation banner.

## 8.4 Empty

Explain why data is absent.

Offer next relevant action.

## 8.5 Error

Show:

- what failed
- retryability
- preserved content
- retry action
- request ID in technical detail

## 8.6 Unavailable

Explain prerequisite.

Example:

```text
Decision extraction is unavailable because the AI provider failed.
Architecture and Timeline remain available.
```

---

## 9. Landing Page

## 9.1 Goal

Start Atlas generation immediately.

## 9.2 Layout

```text
Hero
Repository input
Generate button
Product explanation
Sample repositories
Feature preview
Supported scope
```

## 9.3 Hero Copy

Primary:

```text
Understand any GitHub repository in minutes.
```

Secondary:

```text
Generate an evidence-backed Software Atlas for architecture, subsystems, decisions, history, and ownership.
```

## 9.4 Repository Input

Placeholder:

```text
https://github.com/owner/repository
```

Behavior:

- paste-friendly
- submit with Enter
- disable duplicate submission
- preserve input on error
- normalize valid GitHub URL
- show inline validation

## 9.5 Validation States

### Valid

Show subtle confirmation.

### Invalid Format

```text
Enter a repository root URL, such as:
https://github.com/owner/repository
```

### Private

```text
Trace MVP supports public repositories only.
```

### Unsupported

Explain exact limitation.

### Existing Atlas

```text
Atlas already exists.
```

Primary action:

```text
Open Atlas
```

## 9.6 Acceptance Criteria

- user understands product before scrolling
- repository input is primary visual focus
- invalid input never starts ingestion
- no auth friction
- sample repository opens or generates Atlas

---

## 10. Generation Progress

## 10.1 Goal

Make long-running work understandable and trustworthy.

## 10.2 Layout

```text
Repository identity
Overall progress
Current stage
Stage list
Status explanation
Retry / Open Atlas action
```

## 10.3 Stage List

Example:

```text
✓ Validate repository
✓ Fetch metadata
✓ Fetch source tree
✓ Fetch issues
● Build graph
○ Generate embeddings
○ Discover subsystems
○ Extract decisions
○ Generate Atlas
```

## 10.4 Stage Semantics

- completed: checkmark
- running: active indicator
- queued: muted
- skipped: labeled
- failed: error icon
- retrying: retry indicator

## 10.5 Progress Rules

- progress never moves backward
- page refresh preserves state
- current stage has explanation
- failed stage shows cause
- partial completion can open Atlas
- no fake exact ETA

## 10.6 Failure State

Show:

```text
Decision extraction failed.
Architecture and Timeline are available.
```

Actions:

```text
Open partial Atlas
Retry decision extraction
```

---

## 11. Repository Shell

## 11.1 Header Identity

Display:

```text
owner / repository
```

Secondary metadata:

- primary language
- GitHub link
- status
- last indexed time

## 11.2 Status Badge

Values:

```text
Ready
Partial
Generating
Failed
Reduced analysis
```

## 11.3 Global Search

Shortcut:

```text
Cmd/Ctrl + K
```

Searches:

- files
- symbols
- subsystems
- decisions
- contributors
- issues
- pull requests

---

## 12. Overview Page

## 12.1 Goal

Provide useful repository understanding in under one minute.

## 12.2 Layout

```text
Repository summary
Quick stats
Language chart
Architecture summary
Major subsystems
Suggested learning order
Important decisions
Recent releases
Recent activity
```

## 12.3 Above the Fold

Must show:

- repository name
- concise summary
- major subsystems
- architecture summary
- next recommended action

## 12.4 Repository Summary

Maximum:

```text
2–4 short paragraphs
```

Contains:

- purpose
- primary users
- main technical shape
- important limitations

## 12.5 Statistics

Use compact stat cells.

Examples:

- source files
- contributors
- releases
- issues
- pull requests
- primary language

Do not over-prioritize stars/forks.

## 12.6 Language Distribution

Use `react-chartjs-2`.

Must provide:

- percentage
- labels
- accessible text summary
- no color-only meaning

## 12.7 Major Subsystem Cards

Each shows:

- name
- one-line summary
- confidence label
- file count
- dependency count
- key file
- open action

## 12.8 Suggested Learning Order

Show as ordered list.

Each step:

- title
- rationale
- estimated difficulty
- linked entity

## 12.9 Important Decisions

Show only confirmed decisions by default.

Each card:

- title
- date
- confidence
- evidence count
- affected subsystem

## 12.10 Empty States

### No Decisions

```text
No confirmed decisions found.
Explore related pull requests and issues in Timeline.
```

### No Subsystems

```text
Reliable subsystem boundaries could not be derived.
Architecture falls back to directories and imports.
```

---

## 13. Architecture Page

## 13.1 Goal

Explain system structure visually.

## 13.2 Desktop Layout

```text
┌───────────────────────────────────────────────┐
│ Filters / Search / Legend                     │
├──────────────────────────────┬────────────────┤
│ Graph                        │ Detail Panel   │
│                              │                │
│                              │                │
└──────────────────────────────┴────────────────┘
```

## 13.3 Graph Library

Use:

```text
Cytoscape.js
```

## 13.4 Default Graph

Default nodes:

- confirmed subsystems
- entry points
- major external dependencies

Do not show every file.

## 13.5 Node Visual Rules

Suggested shapes:

- subsystem: rounded rectangle
- file: rectangle
- directory: folder-like rectangle
- external dependency: hexagon
- entry point: emphasized outline

## 13.6 Edge Visual Rules

- deterministic: solid
- derived: dashed
- inferred: dotted
- low confidence: reduced opacity
- selected path: emphasized

Do not rely on color alone.

## 13.7 Controls

- zoom
- pan
- fit
- reset
- search
- filter node types
- filter edge types
- confidence threshold
- show/hide external dependencies
- focus subsystem

## 13.8 Selection

Click node:

- highlight node
- highlight first-degree relations
- open detail panel
- preserve viewport

Click edge:

- show relationship type
- knowledge kind
- confidence
- evidence
- source/target

## 13.9 Detail Panel

Shows:

- name
- type
- summary
- confidence
- evidence action
- key files
- dependencies
- related decisions
- contributors
- metrics
- open full detail

## 13.10 Graph Empty/Failure

If graph unavailable:

```text
Architecture graph could not be generated.
Directory structure and source files remain available.
```

## 13.11 Mobile

Use:

- full-screen graph mode
- bottom-sheet details
- reduced initial nodes
- simplified controls

---

## 14. Subsystems Page

## 14.1 Goal

Let users understand repository by functional concepts.

## 14.2 List Layout

Options:

- compact cards
- table
- graph/list toggle later

Recommended default:

```text
compact card list
```

## 14.3 Subsystem Card

Shows:

- name
- summary
- confidence
- status
- file count
- top dependency
- top contributor
- last activity

## 14.4 Candidate Subsystems

Label:

```text
Candidate
```

Do not mix visually with confirmed without distinction.

## 14.5 Filters

- confidence
- status
- activity
- dependency count
- search

## 14.6 Detail Page

Sections:

```text
Summary
Evidence
Key files
Important symbols
Dependencies
Related decisions
Contributors
Timeline
Suggested next subsystem
```

## 14.7 Discovery Explanation

Show:

```text
Why Trace grouped this subsystem
```

Signals:

- import community
- directory cohesion
- semantic similarity
- documentation
- co-change history

---

## 15. Timeline Page

## 15.1 Goal

Explain repository evolution.

## 15.2 Layout

```text
Activity charts
Filters
Chronological event stream
Event detail drawer
```

## 15.3 Charts

Use `react-chartjs-2`.

Charts:

- activity over time
- release frequency
- contribution trends

## 15.4 Event Stream

Each event shows:

- type
- title
- date
- author
- subsystem
- summary
- source link

## 15.5 Event Type Visuals

Use icon + text.

Never color only.

## 15.6 Filters

- date range
- artifact type
- subsystem
- contributor
- release

## 15.7 Inferred Milestones

Must show:

- inferred badge
- confidence
- evidence action

---

## 16. Decisions Page

## 16.1 Goal

Explain why meaningful changes occurred.

## 16.2 List

Default:

```text
confirmed decisions only
```

Optional filter:

```text
candidate decisions
```

## 16.3 Decision Card

Shows:

- title
- context summary
- decision date
- confidence
- evidence count
- affected subsystem
- implementing PR

## 16.4 Detail Page

Sections:

```text
Context
Decision
Alternatives
Outcome
Evidence chain
Affected files
Affected subsystems
Timeline
```

## 16.5 Evidence Chain UI

```text
Issue / Discussion
    ↓
Pull Request
    ↓
Commit
    ↓
File
```

Each node clickable.

## 16.6 Missing Alternatives

Do not show empty alternatives section.

## 16.7 Insufficient Evidence

Do not render as confirmed.

Optional internal/candidate view:

```text
Trace found a possible decision, but evidence is insufficient.
```

---

## 17. Contributors Page

## 17.1 Goal

Surface likely repository knowledge holders without claiming absolute expertise.

## 17.2 List

Shows:

- avatar
- login
- repository activity
- active subsystems
- recency
- expertise score label

## 17.3 Language

Use:

```text
Strong repository activity
Moderate repository activity
Limited repository evidence
```

Avoid:

```text
Expert
Owner
Best person
```

unless explicit repository metadata supports it.

## 17.4 Contributor Detail

Sections:

```text
Summary
Expertise score breakdown
Active subsystems
Authored pull requests
Reviewed pull requests
Commits
Files
Activity timeline
```

## 17.5 Score Explanation

Display components.

Example:

```text
Authored PRs       30%
Reviewed PRs       20%
Commits            15%
Subsystem files    20%
Recency            15%
```

---

## 18. Explore Page

## 18.1 Goal

Enable direct graph exploration.

## 18.2 Default State

Do not load entire repository graph.

Start with:

- repository node
- major subsystems
- important artifacts

## 18.3 Expansion

User selects:

```text
Expand neighbors
```

Options:

- depth 1–3
- node types
- edge types
- confidence threshold

## 18.4 Detail Panel

Shows:

- entity summary
- metadata
- edges
- confidence
- evidence
- GitHub source
- Atlas links

## 18.5 Graph Safety

- cap visible nodes
- warn before large expansion
- allow reset
- preserve selected path
- no automatic infinite expansion

## 18.6 Search

Search result may:

- focus existing node
- add node to graph
- open entity directly

---

## 19. Ask Page

## 19.1 Goal

Answer focused repository questions after Atlas generation.

## 19.2 Layout

```text
Suggested questions
Conversation
Question input
Answer
Evidence panel
Related entities
```

## 19.3 Suggested Questions

Context-aware examples:

- How does routing work?
- Why was Redis introduced?
- Which files define authentication?
- What changed in latest release?
- Who has worked most on this subsystem?

## 19.4 Input

- multiline
- Enter to submit
- Shift+Enter newline
- max length shown near limit
- disable during submission
- preserve failed prompt

## 19.5 Answer Structure

```text
Direct answer
Confidence
Citations
Limitations
Related files
Related decisions
Timeline context
Possible interpretations
Suggested follow-up
```

## 19.6 Citation Interaction

Citation click:

- opens evidence drawer
- highlights source
- preserves answer position

## 19.7 Confidence

Display:

```text
High confidence
Medium confidence
Low confidence
```

Numeric confidence in details.

## 19.8 Insufficient Evidence

Example:

```text
Trace could not confirm the original reason Redis was introduced.

Related evidence:
- PR #218 added Redis
- Issue #197 discusses retry coordination

Possible interpretation:
Redis may have been introduced for shared retry state.
```

## 19.9 Streaming

MVP may return complete answer.

Future streaming allowed.

Do not stream unverified claims before citation verification.

---

## 20. Evidence Drawer

## 20.1 Goal

Provide one consistent evidence interaction across Trace.

## 20.2 Trigger

Available from:

- summary
- subsystem
- edge
- decision
- contributor score
- Ask citation
- graph node

## 20.3 Layout

```text
Evidence title
Source type
Source artifact
Excerpt
Relationship
Knowledge kind
Confidence
Provenance
Open on GitHub
```

## 20.4 Source Span

For source code:

- path
- line range
- code excerpt
- GitHub link

For issue/PR:

- title
- author
- date
- excerpt
- GitHub link

## 20.5 Knowledge Labels

```text
Repository fact
Graph-derived
AI-inferred
```

## 20.6 Drawer Behavior

- opens from right on desktop
- full-screen sheet on mobile
- deep-linkable later
- back closes drawer
- source links open new tab

---

## 21. Search Overlay

## 21.1 Trigger

```text
Cmd/Ctrl + K
```

## 21.2 Result Groups

- Subsystems
- Files
- Symbols
- Decisions
- Contributors
- Issues
- Pull Requests
- Releases

## 21.3 Keyboard

- arrow keys navigate
- Enter opens
- Escape closes

## 21.4 Result Item

Shows:

- title
- type
- path/context
- confidence if inferred
- source icon

---

## 22. Confidence UX

## 22.1 Bands

```text
High
Medium
Low
```

## 22.2 Rules

### High

Direct but evidence-backed language.

### Medium

Cautious wording.

### Low

Candidate/inference wording.

## 22.3 Display

Primary UI:

```text
Medium confidence
```

Detail:

```text
0.72
```

## 22.4 Tooltips

Explain:

```text
Confidence reflects evidence strength and agreement.
It is not a guaranteed probability.
```

---

## 23. Deterministic vs Inferred UX

Use consistent labels.

### Deterministic

```text
Repository fact
```

### Derived

```text
Graph-derived
```

### Inferred

```text
AI-inferred
```

### Candidate

```text
Candidate inference
```

These labels appear in:

- badges
- evidence drawer
- graph legend
- detail pages

---

## 24. Empty States

## 24.1 No Releases

```text
No GitHub releases found.
Trace uses commits and pull requests for timeline context.
```

## 24.2 No Decisions

```text
No confirmed decisions found.
Explore related issues and pull requests in Timeline.
```

## 24.3 No Review Data

```text
Review activity is unavailable.
Contributor analysis uses commits and authored pull requests.
```

## 24.4 Unsupported Language

```text
Structural source analysis is limited for this language.
Repository history and metadata remain available.
```

## 24.5 No Search Results

```text
No results found.
Try a file name, subsystem, decision, or contributor.
```

---

## 25. Error UX

Every error includes:

- concise title
- cause
- retryability
- preserved state
- next action

Example:

```text
Architecture generation failed

Source files and repository history were indexed successfully.
Retry architecture generation or continue with Timeline.
```

Actions:

```text
Retry
Open Timeline
View technical details
```

---

## 26. Loading UX

## 26.1 Page Loading

Use structural skeleton matching final layout.

## 26.2 Graph Loading

Show:

- graph canvas skeleton
- text: `Preparing architecture graph`

## 26.3 Ask Loading

Show workflow stages optionally:

```text
Classifying question
Retrieving evidence
Expanding graph
Verifying citations
```

Do not expose private chain-of-thought.

---

## 27. Design System

## 27.1 Typography

Use:

- clean sans-serif UI font
- monospace for code, paths, IDs, relationships

Hierarchy:

```text
Page title
Section title
Card title
Body
Metadata
Label
```

## 27.2 Spacing

Use consistent spacing scale.

Dense but breathable.

## 27.3 Borders

Prefer subtle borders over heavy shadows.

## 27.4 Radius

Moderate radius.

Avoid oversized pill-heavy design.

## 27.5 Color

Use restrained neutral palette.

Accent color for:

- selected item
- active navigation
- primary action

Semantic colors for:

- success
- warning
- error
- information

Never encode semantics with color alone.

---

## 28. Core Components

Reusable components:

```text
AppShell
Sidebar
TopBar
PageHeader
StatusBadge
ConfidenceBadge
KnowledgeKindBadge
EvidenceButton
EvidenceDrawer
EntityLink
RepositoryLink
EmptyState
ErrorState
LoadingSkeleton
FilterBar
SearchCommand
MetricCard
ChartCard
GraphCanvas
GraphLegend
DetailPanel
TimelineEvent
DecisionCard
SubsystemCard
ContributorCard
Citation
LimitationBanner
```

---

## 29. Data Tables

Use tables for:

- contributors
- files
- decisions when dense
- evaluation/debug views

Requirements:

- sortable columns
- keyboard accessible
- clear empty state
- sticky header where useful
- pagination
- responsive fallback

---

## 30. Charts

Use `react-chartjs-2`.

Every chart must include:

- title
- legend
- labels
- tooltip
- accessible summary
- empty state
- source note where relevant

Avoid:

- 3D charts
- donut overload
- decorative charts
- misleading truncated axes

---

## 31. Graph Accessibility

Graph must have a non-visual alternative.

Provide:

- node list
- edge list
- keyboard selection
- detail panel
- graph legend
- relationship text

Screen-reader users should access:

```text
Authentication depends on Persistence.
Relationship: inferred.
Confidence: medium.
```

---

## 32. Keyboard Support

Global:

```text
Cmd/Ctrl + K → search
Esc → close overlay/drawer
```

Graph:

- Tab through controls
- arrow/navigation support where practical
- Enter selects focused item
- Reset action keyboard accessible

Ask:

- Enter submits
- Shift+Enter newline

---

## 33. Accessibility

Target:

```text
WCAG 2.2 AA
```

Requirements:

- semantic HTML
- correct headings
- keyboard access
- visible focus
- sufficient contrast
- text alternatives
- reduced motion
- non-color-only states
- labeled controls
- accessible errors
- logical focus management

---

## 34. Responsive Design

## 34.1 Desktop

Primary experience.

Supports:

- side navigation
- split panes
- large graph
- evidence drawer

## 34.2 Tablet

Supports:

- collapsible sidebar
- narrower detail panel
- responsive charts
- full-width cards

## 34.3 Mobile

Supports:

- Overview
- Timeline
- Decisions
- Contributors
- Ask

Reduced graph mode:

- fewer nodes
- full-screen graph
- bottom sheet
- simplified filters

---

## 35. Motion

Use restrained motion.

Allowed:

- drawer transitions
- graph focus transitions
- skeleton fade
- route transition subtle

Avoid:

- auto-moving graph after user selection
- decorative parallax
- bouncing loaders
- long animations

Respect:

```text
prefers-reduced-motion
```

---

## 36. Content Style

Tone:

```text
clear
technical
direct
cautious
evidence-based
```

Avoid:

- “magic”
- “revolutionary”
- “AI knows”
- “definitive”
- unsupported certainty

Preferred wording:

```text
Trace found...
Repository evidence suggests...
This appears to...
Trace could not confirm...
```

---

## 37. Microcopy Rules

## 37.1 Buttons

Use actions:

```text
Generate Atlas
Open Atlas
View Evidence
Open on GitHub
Retry Stage
Expand Neighbors
Ask Trace
```

Avoid:

```text
Submit
Click here
Proceed
```

## 37.2 Status

Use specific text:

```text
Generating embeddings
```

not:

```text
Processing
```

## 37.3 Errors

Use:

```text
Repository is private.
Trace MVP supports public repositories only.
```

not:

```text
Something went wrong.
```

---

## 38. URL and Deep-Link Behavior

Deep-linkable:

- subsystem
- decision
- contributor
- selected graph node later
- Ask query later

Filters should serialize into URL where useful.

Example:

```text
/timeline?type=pull_request&subsystem=auth
```

---

## 39. Performance UX

- render shell immediately
- defer heavy graph loading
- paginate artifact lists
- virtualize long lists later
- cache Atlas pages
- show partial content progressively
- preserve scroll position
- avoid blocking UI on secondary metadata

---

## 40. Analytics Events

Track:

```text
repository_submitted
repository_validation_failed
atlas_generation_started
atlas_generation_completed
atlas_generation_failed
atlas_section_opened
evidence_opened
graph_node_selected
graph_expanded
search_used
question_asked
citation_opened
retry_triggered
```

Do not track sensitive prompt content by default.

---

## 41. UX Acceptance Scenarios

## Scenario A — New User

Given:

- ready Atlas

Then user can:

- understand project purpose
- identify major subsystems
- open architecture
- inspect evidence

without asking a question.

## Scenario B — Partial Atlas

Given:

- decision extraction failed

Then:

- Overview still loads
- limitation visible
- working sections accessible
- retry available

## Scenario C — Low Confidence

Given:

- subsystem confidence low

Then:

- candidate badge visible
- evidence accessible
- not promoted as confirmed major subsystem

## Scenario D — Ask With Weak Evidence

Then:

- limitation shown
- possible interpretation labeled
- no unsupported certainty
- relevant artifacts linked

## Scenario E — Keyboard User

Then:

- can navigate shell
- open search
- inspect evidence
- submit question
- close overlays

without mouse.

---

## 42. Design Delivery Order

Recommended implementation order:

```text
1. Design tokens
2. App shell
3. Landing
4. Progress
5. Overview
6. Evidence drawer
7. Architecture
8. Subsystems
9. Timeline
10. Decisions
11. Contributors
12. Explore
13. Ask
14. Accessibility pass
15. Responsive pass
16. UX testing
```

---

## 43. UX Non-Goals

MVP does not require:

- mobile-first graph editing
- custom graph layout engine
- collaborative annotations
- dark/light theme switch if one polished theme exists
- advanced dashboard personalization
- saved filters
- drag-and-drop graph editing
- chat history across accounts
- onboarding tour with many steps

---

## 44. Definition of UX Success

UX succeeds when:

- users gain value before chat
- architecture is understandable
- evidence is easy to inspect
- uncertainty is visible
- partial failures do not block exploration
- users know what to explore next
- graph does not overwhelm
- technical depth remains accessible
- core flows work by keyboard
- product feels like a Software Atlas, not a generic AI chatbot

---

## Final UX Rule

> Every screen must reduce the effort required to understand software and must never hide where an AI-generated conclusion came from.
