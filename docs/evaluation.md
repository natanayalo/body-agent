# Evaluation & Quality Gates

Reliable behaviour is enforced through layered tests, curated seeds, and coverage thresholds. This document explains how to exercise those layers and what constitutes a blocking failure.

## Test Matrix

| Layer         | Command                                   | Purpose |
|---------------|--------------------------------------------|---------|
| Unit          | `venv/bin/pytest services/api/tests/unit`  | Verify individual nodes, tools, and helpers in isolation. |
| Integration   | `venv/bin/pytest services/api/tests/integration` | Exercise the assembled FastAPI app with stubbed models. |
| Coverage gate | `venv/bin/pytest --cov --cov-report=term-missing` | Enforce ≥95% overall coverage and ≥90% per file via pytest exit codes. |
| Golden evals  | `make eval`                                | Quick regression pass over curated prompt/response pairs. |
| End-to-end    | `make e2e-local`                           | Boots Elasticsearch + API in stub mode and runs the full client flow. |

CI runs the unit + integration suite with coverage by default. Golden and E2E suites are required when touching retrieval, routing, or ingest flows.

## Acceptance Criteria by Surface

- **Retrieval fidelity** — Seeded symptoms must surface at least one relevant snippet (see `services/api/tests/unit/test_health.py`). If BM25 or kNN miss, adjust boosts instead of broadening templates.
- **Risk gating** — `services/api/tests/unit/test_risk_and_critic.py` enforces threshold compliance; regressions that reduce sensitivity below configured levels are release blockers.
- **Streaming contract** — Integration tests assert the presence of streaming deltas, terminal `final` events, and well-formed JSON (`test_graph_stream_basic_query`).
- **Meds onset determinism** — Unit tests cover med facts loading, paraphrase validation, and LLM fallback guardrails. Any new flow must leave citations and disclaimers intact.

## Seeds & Reproducibility

- `seeds/med_facts.json` — Vet meds onset windows; always update alongside tests.
- `seeds/public_medical_kb/` — Markdown snippets consumed by health retrieval; update the E2E fixtures if adding new docs.
- `seeds/providers/` — Deterministic provider catalog for ranking tests.
- In CI, the seed container ensures ingest scripts are idempotent and stub vectors are non-zero. If you add a new seed input, provide a deterministic stub representation for tests.

### Seed Resets

During iterative development you can rerun the ingest scripts:

```bash
docker compose run --rm seed python scripts/ingest_public_kb.py
```

Scripts upsert documents by `_id`, so reruns are safe. If you modify schema fields, bump the `_id` or include migrations in the same PR.

## Manual QA Checklist

Before shipping a user-facing change:

1. Stream a symptom query (`/api/graph/stream`) and confirm SSE ordering, citations, and disclaimer text.
2. Exercise a meds-onset flow with and without feature flags to ensure deterministic fallbacks still work.
3. Run `make e2e-local` if retrieval indices or ingest logic changed.
4. Capture demo steps (≤90s) for the PR template using reproducible commands.

## Tooling & Reporting

- **Coverage reports** — Use `--cov-report=term-missing` to identify uncovered lines. Annotate follow-up tickets if coverage cannot exceed 95% due to third-party code.
- **Pre-commit** — Run `pre-commit run --all-files` before pushing. Hooks include Ruff, Black, MyPy, and secret detection.
- **CI dashboards** — GitHub Actions expose pytest XML, coverage, and lint summaries. Treat any warning about coverage regression as a blocking issue.

Keeping these guardrails in place ensures we ship incremental improvements without compromising safety or determinism.
