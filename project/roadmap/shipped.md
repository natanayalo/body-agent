# Shipped PR Log

Chronicles of recently completed work. Each entry mirrors the acceptance criteria that were previously tracked in `pr-stack.md`.

## PR 24 — Improve meds interaction recall and language-aware answers

- Boosted BM25 fallback with combined medication clauses so interaction docs surface even when embeddings miss.
- Normalized and deduped citations (stripping fragments/`utm_*`) to keep the answer footer clean and stable.
- Threaded `state.language` through answer generation so Hebrew users see localized deterministic + LLM responses; expanded interaction integration coverage.

## PR 23 — Deterministic meds onset answers

- Added `services/api/app/tools/med_facts.py` and seeded `seeds/med_facts.json` with vetted onset windows for acetaminophen/ibuprofen.
- Answer generator now assembles meds-onset replies directly from facts (per language) with exactly one citation and no planner/risk overrides.
- Unit + integration tests cover fact loading, language selection, and Hebrew onset flows.

## PR 22 — Risk gating for meds onset

- Updated `services/api/app/graph/nodes/risk_ml.py` to short-circuit benign meds-onset queries while preserving hard red-flag alerts.
- Tuned thresholds/heuristics so chest-pain and bleeding terms still trigger ML escalation.
- Added parametrized coverage in `services/api/tests/unit/test_risk_and_critic.py`.

## PR 21 — Planner suppression for non-schedule meds flows

- Planner now forces `plan = {"type": "none"}` when `intent == "meds"` and `sub_intent` is not `schedule`.
- Logged suppression decisions for observability and extended planner tests to assert the gating logic.

## PR 20 — Meds sub-intent routing

- Supervisor derives `state["sub_intent"]` via bilingual keyword rules, covering onset, interaction, schedule, side_effects, and refill buckets.
- Persisted sub-intent in graph state so planner/risk/answer nodes can branch deterministically.
- Expanded `services/api/tests/unit/test_supervisor.py` + supervisor/planner combo tests for EN/HE phrases.

## PR 19 — Med normalization (brand → ingredient)

- Introduced `services/api/app/tools/med_normalize.py` with multilingual alias → ingredient mapping and helpers to find meds in text.
- Memory ingest + supervisor normalize detected meds, storing `normalized.ingredient` for consistent comparisons.
- Table-driven coverage in `services/api/tests/unit/test_med_normalize.py` and helper unit tests.

## PR 18 — Language detect & pivot to EN for retrieval

- `scrub` node now tracks `state["language"]` and sets `state["user_query_pivot"]` for non-English inputs.
- Health/risk nodes consume the pivot text for retrieval while preserving the original query for messaging.
- Added HE/EN detection tests in `services/api/tests/unit/test_scrub.py` and integration assertions.

## PR 17 — Review follow-up (docs + copy tweaks)

- Architecture, config, privacy, evaluation, troubleshooting, and roadmap docs landed under `project/` with aligned terminology.
- README streaming example uses `curl --no-buffer`, highlights intent exemplar hot-reload, and notes the `{ "state": ... }` envelope.
- Template fallback keeps risk notices when only pattern templates fire (PR 15 polish).

## PR 16 — Structured symptom registry (doc routing)

- Added `services/api/app/registry/symptoms.yml` with canonical symptom phrases, risk flags, and doc references.
- Introduced loader `app/tools/symptom_registry.py` (cached, env override) and wired `health.run` to inject registry docs ahead of ES search.
- Ensured registry docs dedupe with kNN/BM25 results while preserving language prioritization.
- Seeded abdominal-pain markdown and unit tests verifying registry lookups and ordering.

## PR 15 — Pattern-based fallback (safety templates)

- Added symptom-bucket templates (GI, respiratory, neuro, general) with EN/HE copies to cover no-retrieval cases.
- Template fallback now mirrors recap format: summary, template body, and risk notices before disclaimer/urgent lines.
- Tests cover GI fallback, Hebrew variants, YAML overrides, and risk notice preservation when providers fail.

## PR 14 — Retrieval expansion (query expansion + scoring)

- `health.run` now expands symptom queries via the registry, appending EN synonyms/HE variants before embedding.
- BM25 fallback includes boosted `section:general|warnings` matches and still respects medication-derived terms.
- Added targeted unit coverage for Hebrew stomach-pain flows, ensuring abdominal-pain snippets rise to the top.
- Updated seeds/tests so abdominal-pain guidance is consistently surfaced when available.
