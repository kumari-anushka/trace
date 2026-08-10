# Week 5 Historical Intelligence

Week 5 adds a deterministic historical-intelligence stage that runs after the
architecture and subsystem stages. It deliberately establishes the non-model evidence gate
before generative Ask.

## Decision candidates

The first candidate sources are:

- merged pull requests with changed files;
- release records linked to artifacts or included commits;
- broad commits that modify at least ten snapshot files;
- issues containing explicit design or decision language.

A candidate is only marked `confirmed` when the stored graph contains both context artifacts
and affected files. Other useful changes remain `insufficient_evidence`. The derived decision
node stores context, selected choice, deterministically extracted alternatives, outcome,
confidence, affected files and subsystems, and an evidence-chain summary. Persisted
`IMPLEMENTED_BY`, `DERIVED_FROM`, and `AFFECTS` edges keep these facts traversable.

Model output is not part of confirmation. Rebuilding replaces the stage's previous decision
nodes so stale edges and evidence cannot survive a changed analysis.

## Contributor activity

Contributor activity uses the documented explainable weighting:

```text
0.30 authored pull requests
0.20 reviews
0.15 commits
0.20 subsystem files
0.15 recency
```

Count signals are normalized within the bounded repository history. Recency uses a 180-day
half-life relative to the newest captured activity, which makes reprocessing the same snapshot
deterministic. Metrics include raw and normalized components, weights, active subsystems, a
cautious description, and the explicit limitation that activity does not imply ownership.

## Atlas UI

The Atlas now has Decisions and Contributors views. Confirmed decisions are primary; nearby
changes with incomplete evidence are collapsed under progressive disclosure. Contributor
scores expose their component signals and describe likely repository context rather than
ownership.

The Overview was reduced to the minimum useful snapshot facts. It no longer repeats the full
generated architecture paragraph and only surfaces confirmed subsystems; candidates remain in
the dedicated Subsystems view.

## Repository Ask

`POST /api/repositories/{repository_id}/query` queries the latest stored snapshot. A LangGraph
workflow keeps four responsibilities explicit: plan, retrieve, answer, and verify.

The adaptive planner selects among:

- metadata retrieval for exact terms, paths, artifact identifiers, and recorded history;
- vector retrieval against the active snapshot embedding space;
- graph retrieval after deterministic entity resolution, followed by one-hop traversal.

Results are deduplicated and reranked with reciprocal-rank fusion plus a bounded term-overlap
signal. This makes ranking deterministic and retains every retrieval mode that found a source.

The default answer provider is extractive and requires no external credentials. Opt-in model
synthesis uses the OpenAI Responses API with strict structured output, `store: false`, and the
default `gpt-5.6-sol` model. Enable it with `OPENAI_ASK_ENABLED=true` and `OPENAI_API_KEY`.
Repository content is treated as untrusted prompt data.

Every claim must cite a retrieved evidence ID. The verifier removes empty claims, uncited claims,
and claims that refer to an unknown evidence ID. The API returns the surviving claims, only their
used citations, retrieval modes, and explicit limitations. If nothing survives, it returns a
bounded insufficient-evidence answer rather than a guess.

The focused Ask screen shows only the question composer, citation-verified answer, sources, and
limitations. The Atlas navigation also labels the existing bounded graph explorer as Explore.

## Remaining extensions

- discussion ingestion and decision candidates;
- model-assisted context, choice, alternative, and outcome extraction;
- evaluation fixtures comparing keyword, vector, graph, and hybrid retrieval;
- richer relationship-path citations for multi-hop questions.
