# Trace — UX

## Goal

Help users understand an unfamiliar repository quickly without forcing them into chat first.

## Principles

1. Understand before explore.
2. Visual before conversational.
3. Evidence always reachable.
4. Uncertainty visible.
5. Progressive disclosure.
6. Dense, not cluttered.
7. Consistent entity model.

## Information Architecture

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

## Visual Direction

```text
Linear-like
technical
calm
precise
high-density
evidence-first
```

Avoid:

- chat-first layout
- decorative graphs
- excessive cards
- vague AI language
- oversized marketing UI inside app

## Global States

Every page supports:

```text
loading
ready
partial
empty
error
unavailable
```

## Landing

Primary content:

- tagline
- short explanation
- repository URL input
- Generate Atlas button
- sample repositories
- supported scope

Tagline:

```text
Understand any GitHub repository in minutes.
```

## Progress

Show:

- repository identity
- overall progress
- current stage
- stage list
- failure reason
- retry action
- Open Atlas action

Do not show fake ETA.

## Repository Shell

Desktop:

- left sidebar
- top bar
- main content
- optional right evidence/detail panel

Sidebar:

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

## Overview

Above fold:

- repository summary
- architecture summary
- major subsystems
- next recommended action

Also:

- stats
- language chart
- releases
- decisions
- learning order

## Architecture

Use Cytoscape.js.

Default graph:

- confirmed subsystems
- entry points
- major external dependencies

Rules:

- deterministic edges: solid
- derived edges: dashed
- inferred edges: dotted
- low-confidence: reduced emphasis
- graph bounded
- detail panel on select
- non-visual edge list available

## Subsystems

List shows:

- name
- summary
- confidence
- file count
- top dependency
- top contributor
- last activity

Detail shows:

- discovery signals
- key files
- symbols
- dependencies
- decisions
- contributors
- timeline
- evidence

## Timeline

Use:

- react-chartjs-2 charts
- chronological event list
- filters
- event detail drawer

Event types:

- issue
- PR
- commit
- release
- decision
- milestone

## Decisions

Default:

```text
confirmed decisions only
```

Detail:

- context
- decision
- alternatives
- outcome
- evidence chain
- affected files/subsystems

## Contributors

Show:

- activity
- active subsystems
- recency
- score breakdown

Use:

```text
Strong repository activity
```

Not:

```text
Expert
```

## Explore

Start small.

Allow:

- search
- filters
- bounded expansion
- edge inspection
- evidence
- GitHub links

## Ask

Answer layout:

- direct answer
- confidence
- citations
- limitations
- related files
- related decisions
- graph path
- possible interpretations
- follow-up

Do not stream unverified claims.

## Evidence Drawer

Show:

- source type
- source title
- excerpt
- relationship
- knowledge kind
- confidence
- provenance
- Open on GitHub

Labels:

```text
Repository fact
Graph-derived
AI-inferred
Candidate inference
```

## Search

Shortcut:

```text
Cmd/Ctrl + K
```

Search:

- files
- symbols
- subsystems
- decisions
- contributors
- issues
- PRs
- releases

## Accessibility

Target:

```text
WCAG 2.2 AA
```

Requirements:

- keyboard access
- visible focus
- semantic headings
- sufficient contrast
- chart summaries
- graph text alternative
- reduced motion
- no color-only meaning

## Responsive

Desktop primary.

Mobile supports:

- Overview
- Timeline
- Decisions
- Contributors
- Ask

Graph uses full-screen reduced mode.

## Content Style

Use:

```text
Trace found...
Repository evidence suggests...
Trace could not confirm...
```

Avoid:

```text
AI knows...
Definitively...
Magic...
```

## Success

UX succeeds when:

- users gain value before chat
- graph does not overwhelm
- evidence is easy to inspect
- uncertainty is visible
- partial failures remain usable
- users know what to explore next
