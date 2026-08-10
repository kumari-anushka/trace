# Week 6 — Evaluation and Local Release

Week 6 turns the MVP into a reproducible local portfolio release. It adds executable retrieval
evaluation, repeatable browser coverage, automated accessibility checks, and a concise demo path.

## Release checks

```bash
make infra
make lint
make test
make docker-build
```

`make test` now includes:

- the complete backend unit and PostgreSQL integration suite;
- the frontend production build;
- Playwright checks in desktop Chromium and a Pixel-sized mobile viewport;
- axe-core WCAG A/AA checks for Home, Atlas Overview, and Ask;
- horizontal-overflow assertions at both viewport sizes.

CI runs the same frontend browser suite, audits high-severity npm vulnerabilities, validates all
migrations, and builds both production container targets.

## Evaluation

The versioned development dataset contains eight questions spanning architecture, history,
dependencies, subsystems, contributors, files, and mixed evidence. Each case pins the repository
SHA and stable gold evidence keys.

Run it with:

```bash
make evaluate
```

The evaluator compares keyword, vector, graph, and adaptive hybrid retrieval without changing the
stored embedding-space activation state. See [`evaluation.md`](evaluation.md) for the current
scores and interpretation guardrails.

The evaluator also regenerates the accessible SVG comparison chart used in portfolio materials.

## Five-minute demo

1. Open Home and submit a public GitHub repository.
2. Show persisted ingestion stages; do not promise an ETA.
3. Open Overview and explain the three required snapshot facts.
4. Open Architecture or Explore and inspect one bounded evidence-backed relationship.
5. Open Decisions and show the confirmed-evidence gate.
6. Open Contributors and explain why activity is not ownership.
7. Ask one architecture question, follow a source citation, and expand the limitations.
8. End with the fixed-snapshot evaluation table and its one-repository limitation.

## Known limitations

- Public GitHub repositories only; no authentication or private repository support.
- Python, TypeScript, and JavaScript receive parser-level structural analysis.
- Decision recall is intentionally lower than precision because confirmation requires context and
  affected-file evidence.
- Contributor scores represent recorded activity, not expertise or ownership.
- The local embedding baseline is lexical and weaker than a neural embedding model.
- Citation verification checks citation completeness and source identity; semantic entailment still
  depends on the provider prompt and requires broader evaluation.
- The development benchmark is too small and narrow for statistical or generalization claims.
- The release is reproducible locally with Docker Compose; public hosting is not configured.

## Release status

The reproducible local release path is verified: both production image targets build, Compose
rebuilds and starts the complete application, migrations exit successfully, every long-running
service becomes healthy, the API health check returns `ok`, and the frontend returns HTTP 200.

A hosted deployment, release tag, recorded demo, and multi-repository study remain explicit
post-MVP or publishing work.
