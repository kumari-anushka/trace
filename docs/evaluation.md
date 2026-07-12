# Trace — Evaluation

## Research Question

> Does an adaptive graph-augmented Software Atlas improve unfamiliar-repository understanding compared with vector-only retrieval?

## Baselines

1. GitHub + README
2. Keyword retrieval
3. Vector-only RAG
4. Graph-only retrieval
5. Adaptive hybrid retrieval

## Dataset

Development:

```text
3–5 repositories
30–50 QA cases
```

MSc-level target:

```text
8–12 repositories
200–300 QA cases
12–30 human participants
```

Repositories should vary by:

- language
- size
- activity
- contributor count
- documentation quality
- issue/PR richness

Use fixed snapshot SHAs.

## QA Case

```json
{
  "repository": "owner/name",
  "snapshot_sha": "abc123",
  "question": "Why was Redis introduced?",
  "category": "decision",
  "expected_answer": "...",
  "gold_evidence": ["issue:197", "pr:218"],
  "difficulty": "medium"
}
```

Categories:

- overview
- architecture
- subsystem
- dependency
- decision
- historical
- contributor
- file
- symbol
- mixed

## Retrieval Metrics

- Precision@k
- Recall@k
- Hit Rate@k
- MRR
- nDCG@k
- evidence coverage

## Generation Metrics

- faithfulness
- correctness
- relevance
- completeness
- citation correctness
- citation completeness
- unsupported claim rate
- claim support rate

## Graph Metrics

- entity precision/recall
- edge precision/recall
- path correctness
- invalid edge rate
- graph coverage

## Subsystem Metrics

- graph cohesion
- semantic cohesion
- modularity
- separation
- stability
- human label quality
- practical usefulness

## Decision Metrics

Primary:

```text
confirmed decision precision
```

Also:

- recall
- field accuracy
- evidence-chain completeness
- status accuracy

## Contributor Metrics

Compare against:

- commit-count baseline
- review history
- CODEOWNERS where available
- maintainer judgment

Metrics:

- Spearman correlation
- Kendall tau
- top-k agreement
- usefulness rating

## Human Study

Preferred design:

```text
within-subject crossover
```

Participants use:

- GitHub + README on one repository
- Trace on another

Tasks:

- summarize purpose
- identify architecture
- identify subsystem
- explain decision
- locate implementation files
- identify likely contributor

Measure:

- completion time
- correctness
- evidence quality
- confidence
- perceived understanding
- usability

## Ablations

- no graph
- no vector retrieval
- no reranker
- no citation verification
- directory-only subsystems
- no historical signals

## Fair Comparison

Keep constant:

- snapshot
- questions
- generator model
- token budget
- temperature
- output schema
- timeout

Only retrieval strategy changes.

## Operational Metrics

- ingestion time
- stage duration
- Ask latency
- token usage
- cost
- provider failure rate
- cache hit rate
- storage size

## Initial Targets

```text
Recall@10 >= 0.80
Citation correctness >= 0.90
Unsupported claim rate <= 0.10
Confirmed decision precision >= 0.85
Median Ask latency <= 15s
```

Targets are hypotheses, not guarantees.

## Reproducibility

Store:

- repository SHA
- dataset version
- parser version
- ontology version
- graph algorithm version
- chunking version
- embedding model
- LLM model
- prompt version
- retrieval config
- random seed

## Reporting

Each experiment report includes:

- objective
- dataset
- systems
- configuration
- results
- statistics
- error analysis
- latency
- cost
- limitations
- conclusion

## Key Rule

Judge Trace by measurable understanding and evidence quality, not impressive generated text.
