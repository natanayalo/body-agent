Here’s a crisp next-step plan you can ship as a sequence of small PRs, each with concrete acceptance criteria and code pointers.

---

# Current PR — PR 15 — Pattern-based fallback (safety templates)

Why: Provide minimal, safe guidance when retrieval returns nothing.

Scope

- Add a small, reviewed template set keyed by coarse symptom buckets (e.g., GI, respiratory, neuro), localized EN/HE.
- Trigger only when no snippets were found; always include disclaimers and escalation conditions.

Acceptance

- Unit tests assert GI queries yield a GI template when KB is empty; includes disclaimer and no diagnosis language.

Pointers

- `services/api/app/graph/nodes/answer_gen.py` — fallback builder consults template map before generic recap.

---

# Next PR Stack (Flexibility for Symptoms)

These PRs broaden symptom coverage beyond fixed phrases and improve relevance for queries like stomach pain without hardcoding per-case logic.

<!-- PR 13 shipped: Intent exemplars registry (+ multilingual) -->

## PR 14 — Retrieval expansion (query expansion + scoring)

Why: Find relevant guidance when exact keywords aren’t present.

Scope

- Add lightweight synonym/translation map for common symptoms (e.g., "כאבי בטן" → ["stomach pain", "abdominal pain"]).
- Apply expansion before ES search; boost matches in `section: general|warnings` more than other sections.
- Keep language prioritization; prefer docs in `state.language`.

Acceptance

- Hebrew stomach-pain query retrieves abdominal-pain guidance when present.
- Unit tests cover expansion and section boosting; integration proves improved snippet relevance.

Pointers

- `services/api/app/graph/nodes/health.py` — inject expanded terms into kNN/BM25; adjust `should` clauses and boosts.

## PR 16 — Structured symptom registry (doc routing)

Why: Fast path to vetted pages without brittle keywords.

Scope

- Introduce `symptoms.yml` mapping canonical symptom names → doc IDs/URLs + risk flags and language variants.
- On match, add the mapped docs directly to `public_snippets` (deduped) before ES search.

Acceptance

- Registry hit yields the mapped documents at the top; unit tests verify ordering and dedupe.

Pointers

- New loader module under `services/api/app/data/` + hook in `health.run` pre-query.

## PR 17 — KB seeding & translation pipeline

Why: Ensure coverage for core symptoms in Hebrew.

Scope

- Extend `scripts/ingest_public_kb.py` to accept a symptom list and fetch/translate selected pages to HE (store provenance).
- Add a make target (`make seed-he`) to populate fresh bilingual docs.

Acceptance

- CI/dev “seed HE” flow creates HE docs; retrieval prioritizes them; integration tests updated.

Pointers

- `scripts/ingest_public_kb.py`, `docker-compose.yml` volumes; README instructions.

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
