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

# Next PR Stack (Flexibility for Symptoms)

Remaining work focuses on overlaying OTC safety guardrails on top of the richer symptom retrieval flow shipped in PRs 14–16.

<!-- PR 13 shipped: Intent exemplars registry (+ multilingual) -->

---

# PR 18 — Lightweight meds registry (OTC classes + guardrails)

Why: Provide high coverage for “what can I take…” questions without adding many KB pages by using a tiny, structured registry of common OTC classes and safety guardrails.

Scope

- Add `services/api/app/data/med_classes.yml` with a handful of OTC classes (e.g., `acetaminophen`, `ibuprofen`, `naproxen`, `antacids`, `oral_rehydration_salts`). Each item includes: `aliases`, `uses`, `avoid_if`, `interactions` (e.g., NSAIDs ↔ anticoagulants), `age_limits`, `pregnancy`, `notes`.
- New loader `app/tools/meds_registry.py` reading from `MED_CLASSES_PATH` and hot-reloading in dev (`MED_CLASSES_WATCH=true`).
- In `answer_gen.run`, when intent is `symptom` and the user phrasing suggests OTC relief (e.g., “what can I take”, “can I take …”), add a short “OTC options and safety” section sourced from the registry. Never provide dosing; prioritize retrieved snippets when present; fall back to registry guardrails if retrieval is sparse.
- Interaction awareness: if `memory_facts` include anticoagulants (e.g., warfarin), add a caution bullet for NSAIDs (from the registry) without prescribing behavior.
- Config: add `MED_CLASSES_PATH` (default to the repo example under `/app/data/med_classes.yml`) and `MED_CLASSES_WATCH` to `.env.example` and README.
- i18n: keep the registry English-first; surface localized phrasing via existing fallback templates (PR 15) when applicable.

Acceptance

- With no new KB docs, a stomach-pain query yields an answer that includes a concise OTC/safety section (e.g., antacids, general caution on NSAIDs) plus standard disclaimer; no dosing text appears.
- If `memory_facts` contain warfarin, the answer includes an NSAID bleeding-risk caution; removing warfarin removes that caution.
- Works alongside PR 14 (retrieval expansion) and PR 15 (fallback templates) — when relevant GI docs exist, they rank first; registry content supplements rather than replaces them.
- Unit tests cover: registry loading, anticoagulant caution injection, and that dosing is omitted.

Pointers

- `services/api/app/graph/nodes/answer_gen.py` — inject registry-backed “OTC options and safety” section under guardrails.
- `services/api/app/tools/meds_registry.py` — new module to load/watch `med_classes.yml`.
- `.env.example`/README — document `MED_CLASSES_PATH`, `MED_CLASSES_WATCH` defaults.
