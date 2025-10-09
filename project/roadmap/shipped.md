# Shipped PR Log

Chronicles of recently completed work. Each entry mirrors the acceptance criteria that were previously tracked in `pr-stack.md`.

## PR 36 — Planner rationale templates

**owner:** @natanayalo
**status:** SHIPPED
**rollback/flag:** `PLANNER_RATIONALE_ENABLED=false`

- Added localized EN/HE rationale strings summarizing distance, travel limits, hours, and preferred kinds when matching providers are suggested.
- Persisted rationale text on the planner plan payload and surfaced it as the primary explanation entry for REST/SSE responses without exposing raw PII.
- Extended planner, places, and golden tests to cover rationale assembly across preference/no-preference flows while keeping existing acceptance checks green.

**Demo:**
```bash
curl -s http://localhost:8000/api/graph/run \
  -H 'content-type: application/json' \
  -d '{"user_id":"demo","query":"Please book a cardiology clinic tomorrow morning","preferences":{"max_travel_km":5}}' \
  | jq '.state.plan.explanations'
```


## PR 37 — Preference-aware provider scoring

**owner:** @natanayalo
**status:** SHIPPED
**rollback/flag:** set `PREFERENCE_SCORING_WEIGHTS=semantic:1.0,distance:0.0,hours:0.0,insurance:0.0`

- Introduced configurable weighting for semantic, distance, hours, and insurance factors with normalized parsing + safe fallbacks.
- Places node emits structured `matched_insurance_label`, and planner rationales surface insurance matches in EN/HE without duplicating logic.
- Expanded unit + golden tests covering weight permutations, insurance fallbacks, and preference fetching to keep coverage ≥95%.

**Demo:**
```bash
curl -s http://localhost:8000/api/graph/run \
  -H 'content-type: application/json' \
  -d '{"user_id":"demo","query":"Find an endocrinologist","preferences":{"insurance_plan":"maccabi","max_travel_km":10}}' \
  | jq '.state.candidates | map({name, score, reasons})'
```


## PR 34 — Outbound domain allow-list (fail-closed)

**owner:** @natanayalo
**status:** SHIPPED
**rollback/flag:** unset `OUTBOUND_ALLOWLIST` (reverts to allow-all)

- Added `safe_request`/`safe_get` helpers that enforce a configurable outbound allow-list, cover subdomains/IPs, and fail fast on redirects.
- Documented `OUTBOUND_ALLOWLIST` expectations across contributor docs so deploys stay fail-closed by default.
- Expanded `test_http` coverage for case/whitespace handling, partial-domain rejection, IP-validation, and redirect blocking.

**Demo:**
```bash
curl -s http://localhost:8000/api/graph/run \
  -H 'content-type: application/json' \
  -d '{"user_id":"demo","query":"Check my provider list"}' \
  | jq '.state.debug.http_guard'
```

## PR 35 — Preference expansion (distance filter)

**owner:** @natanayalo
**status:** SHIPPED
**rollback/flag:** set `PREFERENCE_TRAVEL_LIMIT_ENABLED=false`

- Normalize `max_travel_km` user preferences so memory/places share one canonical field.
- Filter provider candidates beyond the configured travel radius while preferring in-range locations during dedupe.
- Surface the applied travel limit in planner reasons and cover edge cases with unit + golden tests.

**Demo:**
```bash
curl -s http://localhost:8000/api/graph/run \
  -H 'content-type: application/json' \
  -d '{"user_id":"demo","query":"Find a cardiology clinic","preferences":{"max_travel_km":5}}' \
  | jq '.state.candidates | map({name, distance_km, reasons})'
```

## PR 28 — SSE contract test

- Strengthened `/api/graph/stream` integration test to assert `text/event-stream` headers, at least one streaming `delta`, and a terminal `final` event.
- Ensured the SSE test reuses parsed payloads instead of re-reading the raw stream, avoiding duplicate parsing logic.
- Verified error-path coverage still emits an `error` event when streaming fails.

## PR 29 — Docs: architecture/config/evaluation roll-up

- Published durable contributor docs under `docs/`: architecture overview, configuration matrix, and evaluation guide.
- Linked the new documentation from `README.md` so newcomers can find architecture, config, and quality guardrails.
- Clarified seed idempotency and testing expectations to keep deterministic workflows aligned with CI.

## PR 30 — Intent exemplar refresh + hot reload polish

- Supervisor watcher now tracks both exemplar file path and `st_mtime_ns`, reloading cleanly on edits, deletes, or path changes.
- `_load_exemplars` uses real temp files in unit tests to cover JSON/JSONL parsing, malformed content, and dynamic watcher behaviour.
- Full test suite passes with deterministic reload coverage to support hot-reload workflows.

## PR 31 — PII scrub expansion

- Extended `scrub` to redact government IDs and address fragments with `[gov_id]` and `[address]` tokens alongside existing `[ssn]`, `[phone]`, and `[email]`.
- Moved all scrubber regexes to module-level compiled patterns for performance; ordered redactions so SSNs are recognized first, then generalized gov-ID phrases.
- Added EN/HE unit tests, including multi-word Hebrew streets and long English street names, asserting both token presence and removal of the original PII fragments.

## PR 32 — Request ID propagation (end-to-end)

- `/api/graph/run` and `/api/graph/stream` now accept/emit `request_id`, defaulting to UUIDv4 when the header is absent.
- SSE deltas/final/error events include the `request_id`; `state.debug.request_id` matches the non-streaming response.
- Logging pipeline uses a contextvar filter to prefix log lines with `rid=…`; integration tests cover header override and generation.

## PR 33 — Risk eval harness (golden tests)

- Added `seeds/evals/risk/en.jsonl` and `services/api/tests/golden/risk/test_eval_risk.py` to run stubbed classifier cases and print a label summary.
- `make eval-risk` target runs only the risk golden suite for quick regression checks.
- Golden runs fail fast on malformed JSONL so seed issues surface immediately.

## PR 27 — Seed container idempotent + stub-aware

- Updated `scripts/ingest_public_kb.py` and `scripts/ingest_providers.py` to upsert on `_id`, skip redundant writes, and fill stub vectors so reruns leave ES ready for tests.
- Added guardrails to fail fast when embeddings stay zero-length and to respect stub mode toggles in CI/local flows.
- Refresh docs to describe deterministic reruns and how to reset stub data without manual cleanup.

## PR 26 — LLM neutral fallback for onset (flagged)

- Added `ONSET_LLM_FALLBACK` flag and language-aware neutral blurb generation when no deterministic onset fact exists.
- Validator rejects numeric/time tokens so the fallback never introduces dosing or timing claims; falls back to templates on violations.
- Unit coverage exercises enabled/disabled flows plus regression tests for Hebrew/English copies.

## PR 25 — Paraphrase onset facts via Ollama (flagged)

- Introduced `PARAPHRASE_ONSET` flag that calls the configured Ollama model to rewrite deterministic onset snippets while preserving numeric facts.
- Added strict diffing to ensure paraphrased summaries retain all numbers and citations; gracefully degrades to canonical copy on failure.
- Documented the new flag across README/config and added unit tests for validator edge cases and multilingual paraphrases.

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
