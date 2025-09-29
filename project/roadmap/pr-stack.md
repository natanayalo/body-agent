Here’s a crisp next-step plan you can ship as a sequence of small PRs, each with concrete acceptance criteria and code pointers.

---

# Current PR — PR 17 — KB seeding & translation pipeline

Why: Ensure coverage for core symptoms in Hebrew.

Scope

- Extend `scripts/ingest_public_kb.py` to accept a symptom list and fetch/translate selected pages to HE (store provenance).
- Add a make target (`make seed-he`) to populate fresh bilingual docs.

Acceptance

- CI/dev “seed HE” flow creates HE docs; retrieval prioritizes them; integration tests updated.

Pointers

- `scripts/ingest_public_kb.py`, `docker-compose.yml` volumes; README instructions.

---

## Review Follow‑Up (High‑ROI docs + copy tweaks)

- Architecture & sequences: added `project/architecture.md` (block diagram; med‑interaction and appointment sequences; ES hits; SSE order; run/stream envelope).
- Config reference & modes: added `project/config.md` (env table; CI stub vs. local mode guidance).
- Data seeding clarity: README now states the seed container auto‑populates indices on `docker compose up` (single source of truth).
- Privacy & safety: added `project/privacy.md` (scrubbed fields, encryption at rest, disclaimers, risk gating).
- Evaluation & quality: added `project/evaluation.md` (test matrix; RAG recall; thresholds; SSE contract; fixtures).
- Troubleshooting / Ops: added `project/troubleshooting.md` (vector dims, permissions, health checks/logs).
- Roadmap page: added `project/roadmap.md` (Now / Next / Later milestones).
- Template fallback preserves risk notice formatting even when only pattern templates fire (PR 15 follow-up).

Copy/structure tweaks in README:

- Streaming example uses `curl --no-buffer` and notes that the `final` event is last.
- Intent exemplars section surfaces the default location + hot‑reload knob early (points to `/app/data/intent_exemplars.jsonl`).
- Noted that `/api/graph/run` returns a stable `{ "state": ... }` envelope.

# Shipped — PR 16 — Structured symptom registry (doc routing)

- Added `services/api/app/registry/symptoms.yml` with canonical symptom phrases, risk flags, and doc references.
- Introduced loader `app/tools/symptom_registry.py` (cached, env override) and wired `health.run` to inject registry docs ahead of ES search.
- Ensured registry docs dedupe with kNN/BM25 results while preserving language prioritization.
- Seeded abdominal-pain markdown and unit tests verifying registry lookups and ordering.

# Shipped — PR 15 — Pattern-based fallback (safety templates)

- Added symptom-bucket templates (GI, respiratory, neuro, general) with EN/HE copies to cover no-retrieval cases.
- Template fallback now mirrors recap format: summary, template body, and risk notices before disclaimer/urgent lines.
- Tests cover GI fallback, Hebrew variants, YAML overrides, and risk notice preservation when providers fail.

# Shipped — PR 14 — Retrieval expansion (query expansion + scoring)

- `health.run` now expands symptom queries via the registry, appending EN synonyms/HE variants before embedding.
- BM25 fallback includes boosted `section:general|warnings` matches and still respects medication-derived terms.
- Added targeted unit coverage for Hebrew stomach-pain flows, ensuring abdominal-pain snippets rise to the top.
- Updated seeds/tests so abdominal-pain guidance is consistently surfaced when available.

# Next PR Stack — Milestone 1: Meds “onset” relevance & safety

The next wave targets language-aware retrieval, meds normalization, and deterministic onset guidance so Hebrew users get the right information without unnecessary risk notices.

<!-- PR 13 shipped: Intent exemplars registry (+ multilingual) -->

## PR 18 — Language detect & pivot to EN for retrieval

Why: Hebrew queries currently pull noisy EN snippets; we need a stable signal for downstream nodes.

Scope

- `services/api/app/graph/nodes/scrub.py` — detect language (fast heuristic now; MT later) and store `state["language"]`.
- If `language != "en"`, populate `state["user_query_pivot"]` with a placeholder HE→EN translation helper.
- Thread the pivoted text through health/risk retrieval (default to original text when EN).

Acceptance

- HE query yields `state.language == "he"` and non-empty `state.user_query_pivot`.
- Health retrieval for HE symptom no longer surfaces irrelevant ibuprofen/warfarin when absent from query/memory.
- Unit coverage for HE/EN detection + pivot wiring.

Pointers

- `services/api/app/graph/nodes/scrub.py`, `services/api/app/graph/nodes/health.py`, `services/api/tests/unit/test_scrub.py`.

## PR 19 — Med normalization (brand → ingredient, multilingual)

Why: We need consistent ingredient matching (e.g., אקמול → acetaminophen) for lookup, risk, and KB joins.

Scope

- New helper `services/api/app/tools/med_normalize.py` with a minimal lexicon + API.
- Use during memory ingest/supervisor to populate `memory_facts[].normalized.ingredient` and inline detections.

Acceptance

- Common IL brands resolve to their ingredients (אקמול → acetaminophen, נורופן → ibuprofen).
- Memory facts include `normalized.ingredient` when appropriate; supervisor uses the normalized value for comparisons.
- Table-driven tests in `services/api/tests/unit/test_med_normalize.py`.

## PR 20 — Meds sub-intent classification

Why: Separate onset/schedule/interaction flows so planner + risk respond appropriately.

Scope

- Extend supervisor to derive `state["sub_intent"]` via light keyword rules in EN/HE.
- Cover onset, interaction, schedule, side_effects, refill buckets (fallback `None`).

Acceptance

- “מתי זה אמור להשפיע” and “when will it start working” → `sub_intent="onset"`.
- “אפשר לקחת עם …” / “interaction with …” → `sub_intent="interaction"`.
- Unit expectations in `services/api/tests/unit/test_supervisor.py`.

## PR 21 — Planner suppression for non-schedule meds flows

Why: Prevent auto-generated schedules when user only wants onset guidance.

Scope

- In planner node, when `intent == "meds"` and `sub_intent != "schedule"`, force `plan = {"type": "none"}`.

Acceptance

- Meds onset queries return no plan.
- Planner tests extended to cover gating logic.

## PR 22 — Risk gating for meds:onset

Why: Reduce false urgency where onset guidance is benign while keeping true red flags.

Scope

- In `risk_ml`, short-circuit or raise thresholds when `intent == "meds"` and `sub_intent == "onset"` unless hard red-flag terms are present.

Acceptance

- Safe onset queries produce no ML alerts; “chest pain” / “bleeding” still trigger.
- Parametrised coverage in `services/api/tests/unit/test_risk_and_critic.py`.

## PR 23 — Deterministic med facts micro-KB (onset/dose metadata)

Why: Provide clear, localized onset guidance with citations instead of LLM guesswork.

Scope

- Seed `seeds/med_facts.json` with onset windows + sources for acetaminophen/ibuprofen (expandable).
- New helper `services/api/app/tools/med_facts.py` exposing `onset_for(ingredient)`.
- In `answer_gen`, when `intent == "meds"` and `sub_intent == "onset"`, compose an answer from the facts in the user’s language; include a citation.

Acceptance

- “אקמול מתי משפיע” returns 30–60 minute onset (in HE), no planner, no risk alert, exactly one citation.
- Unit tests for helper + answer path; integration happy-path covering HE.

---

# Milestone 2 — Retrieval quality & cleanliness

## PR 24 — Health BM25 fallback with med boosts

Why: When kNN misses, ensure BM25 still surfaces interaction docs tied to the user’s meds.

Scope

- In BM25 fallback, include boosted `match` clauses for each med’s title/text plus the primary query/pivot; keep `minimum_should_match = 1`.
- Add integration coverage for the dual-med interaction flow.

Acceptance

- Interaction documents retrieved when user memory has two interacting meds.
- `tests/integration/test_api_integration.py::test_e2e_medication_interaction_flow` updated.

## PR 25 — Citation dedupe & URL normalization

Why: Avoid duplicate citations when docs arrive via registry + search.

Scope

- Introduce `url_normalize` (strip fragments + UTM params) and dedupe citations while preserving order.
- Unit tests for normalization + dedupe behaviour.

## PR 26 — Language-aware answer rendering

Why: Answers should default to the user’s language, not always English.

Scope

- `answer_gen` chooses templates/prompts using `state.language` (fallback EN).
- Tests ensure HE queries yield HE answers while EN remains unchanged.

## PR 32 — Paraphrase onset facts via Ollama (flagged)

Why: Improve readability/localization of deterministic onset answers without altering facts.

Scope

- Add optional `PARAPHRASE_ONSET=true|false` env flag (default false).
- When a med fact exists, call Ollama to paraphrase the given `summary`/`follow_up` in the user’s language.
- Enforce validators to block any added numbers/claims; always append `Source: {label}`; keep citation URL from facts.

Acceptance

- With the flag on, onset answers remain factually identical (numbers unchanged) but are paraphrased; exactly one citation.
- With the flag off, current deterministic rendering is used.
- Unit tests cover validator behavior and flag on/off.

Pointers

- `services/api/app/graph/nodes/answer_gen.py`, `.env.example` entries, new tests under `services/api/tests/unit/test_answer_gen.py`.

## PR 33 — LLM neutral fallback for onset (no fact; flagged)

Why: Provide helpful guidance when no onset fact exists without guessing timings or dosing.

Scope

- Add optional `ONSET_LLM_FALLBACK=true|false` env flag (default false).
- When `onset_for(...)` returns None, generate a short neutral blurb (no numbers/times) and disclaimer; no citation.
- Enforce validators to reject any numeric/time tokens.

Acceptance

- With the flag on and no fact present, onset answers contain no timings/doses and include the disclaimer.
- With the flag off, existing pattern/template fallback is used.
- Unit tests assert no-number/no-time validation and flag behavior.

Pointers

- `services/api/app/graph/nodes/answer_gen.py`, `.env.example`, tests in `services/api/tests/unit/test_answer_gen.py`.

---

# Milestone 3 — Stability & CI polish

## PR 27 — Seed container idempotent + stub-aware

- Ensure ingest scripts produce non-zero stub vectors, upsert by ID, and can rerun safely (especially in CI).
- Smoke validation via existing E2E suite.

## PR 28 — SSE contract test

- Extend streaming integration test to assert `content-type: text/event-stream`, at least one `delta`, and `final` arrives last.

## PR 29 — Docs: architecture/config/evaluation roll-up

- Publish the drafted docs (`docs/architecture.md`, `docs/config.md`, `docs/evaluation.md`) and link from README.

---

# Milestone 4 — Intent + privacy hardening

## PR 30 — Intent exemplar refresh + hot reload polish

- Ensure `INTENT_EXEMPLARS_PATH` watcher works end-to-end; add unit coverage for loader.

## PR 31 — PII scrub expansion

- Extend scrubber regexes for gov IDs and address fragments; redact to `[gov_id]` / `[address]`; cover with unit tests.
