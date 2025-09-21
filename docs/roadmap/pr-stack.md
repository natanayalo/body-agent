Here’s a crisp next-step plan you can ship as a sequence of small PRs, each with concrete acceptance criteria and code pointers.

---

# PR 7 — Real **LangGraph StateGraph** + **streaming API**

**Why:** You currently run a linear pipeline. Moving to StateGraph makes routing explicit, easier to extend, and lets us stream partial results to the UI/CLI.

**Scope**

* Replace the linear calls in `main.py` with a compiled `StateGraph`.
* Add conditional edges for `meds`, `symptom`, `appointment`, `other`.
* Introduce an **SSE/NDJSON streaming** endpoint `/api/graph/stream` that yields node-by-node events.
* Keep `/api/graph/run` stable (returns the final `state`).

**Sketch**

```python
# services/api/app/graph/build.py
from langgraph.graph import StateGraph, END
from app.graph.state import BodyState
from app.graph.nodes import supervisor, scrub, memory, health, risk_ml, places, planner, critic

def build_graph():
    g = StateGraph(BodyState)
    g.add_node("supervisor", supervisor.run)
    g.add_node("scrub", scrub.run)
    g.add_node("memory", memory.run)
    g.add_node("health", health.run)
    g.add_node("risk_ml", risk_ml.run)
    g.add_node("places", places.run)
    g.add_node("planner", planner.run)
    g.add_node("critic", critic.run)

    g.set_entry_point("scrub")
    g.add_edge("scrub", "supervisor")
    g.add_edge("supervisor", "memory")
    # branches
    g.add_conditional_edges("memory", lambda s: s["intent"], {
        "meds": "health",
        "symptom": "health",
        "appointment": "places",
        "other": "planner",
    })
    g.add_edge("health", "risk_ml")
    # converge
    for n in ("risk_ml", "places", "planner"):
        g.add_edge(n, "critic")
    g.add_edge("critic", END)
    return g.compile()
```

**Acceptance**

* `/api/graph/run` returns identical or better results vs. current linear path.
* `/api/graph/stream` emits events like:

  ```json
  {"node":"memory","delta":{"memory_facts":[...]}}
  {"node":"health","delta":{"public_snippets":[...]}}
  {"node":"risk_ml","delta":{"debug":{"scores":{...},"triggered":[...]}}}
  {"final":{"state":{...}}}
  ```
* Tests cover: supervisor routing, stream yields, and that **redacted** text is what leaves `scrub`.

---

# PR 8 — **Encryption & tenancy** (APP\_DATA\_DIR is set; now protect private memory)

**Why:** You promised privacy-first. Add real protection for `private_user_memory` and make it multi-tenant-safe.

**Scope**

* **Field-level encryption** for `private_user_memory.value` (and any future sensitive fields).
* Use **libsodium (PyNaCl)** sealed boxes or **cryptography.Fernet** with per-user key material.
* Keys: for dev, store per-user keys under `${APP_DATA_DIR}/keys/<user_id>.key`; abstract behind `crypto.py`.
* ES docs remain searchable via **embedding** on the plaintext the user submits at runtime; only the stored value is encrypted at rest.
* Add `user_id` partitioning to all ES reads/writes; enforce in queries.

**Sketch**

```python
# services/api/app/tools/crypto.py
from cryptography.fernet import Fernet
def get_user_cipher(user_id: str) -> Fernet: ...
def encrypt_for_user(user_id: str, text: str) -> str: ...
def decrypt_for_user(user_id: str, token: str) -> str: ...
```

```python
# in add_med
enc_value = encrypt_for_user(m.user_id, m.value)
doc = {..., "value": enc_value, "value_encrypted": True, ...}
```

**Acceptance**

* New integration test: add a med with `value="Taking 1 tablet..."` -> ES document **does not** contain the plaintext.
* Decryption path verified via a GET helper or internal read.
* All ES queries include `{"term":{"user_id": "<id>"}}` guard.

---

# PR 9 — **Provider ranking + preferences** (actual decision-making)

**Why:** Make “book near me” feel smart.

**Scope**

* Add a **preferences** object in private memory (`max_distance_km`, `preferred_kinds`, `hours_window`, `insurance_plan` placeholder).
* In `places.run`, compute a score: RRF on (semantic score, distance score, hours fit), then return ranked `candidates` with **reasons**.
* Add a simple “explanations” list to `plan` (“Chose Dizengoff Lab: closest + open tomorrow 07:00-14:00”).

**Sketch**

```python
# places.py
def _score(c, qvec, user_prefs):
    s = 0.6*semantic + 0.25*distance + 0.15*hours_fit
    reasons = [...]
    return s, reasons
```

**Acceptance**

* Deterministic ranking given the seed providers.
* Plan includes `provider` + `reasons` array.
* Test asserts ordering flips when `preferred_kinds=["clinic"]`.

---

# PR 10 — **Evaluation harness** (golden set)

**Why:** Prevent regressions as graph grows.

**Scope**

* `tests/golden/inputs.jsonl` with prompts (EN + HE) and expected intent, ≥1 citation domains, and risk triggers.
* `tests/test_golden.py` loads inputs; runs `/api/graph/run` **with stubbed risk** and asserts:

  * correct intent
  * at least one citation (after seeding)
  * deduped citations; alerts present when expected
* Add a `make eval` target to run this suite locally.

**Acceptance**

* CI gate runs golden tests on every PR.
* Flaky behavior minimized with stubs and seeded indices.

---

# PR 11 — **LLM generation (local-first)** + safer responses

**Why:** Turn snippets + risk signals into helpful, cited output.

**Scope**

* Plug an LLM (Ollama-first; OpenAI optional) behind `LLM_PROVIDER`.
* New node `answer_gen.run(state)`:

  * Inputs: `public_snippets`, `risk_ml.triggered`, `memory_facts`
  * Output: `messages += [{"role":"assistant","content": "...", "citations":[...]}]`
* Guardrails:

  * Insert standard **medical disclaimer** + “when to seek urgent care” if `urgent_care` or `see_doctor` fired.
  * **No diagnosis** language; cite sources (`citations` list).

**Acceptance**

* With `LLM_PROVIDER=none`, pipeline still works (skips `answer_gen`).
* With Ollama available, `messages[-1].content` is non-empty and contains at least one citation marker, risk-aware advice, and no PII.

---

# PR 12 — **i18n & language detection**

**Why:** You’re in IL and already testing Hebrew.

**Scope**

* Add lightweight language detection (`langdetect` or `fasttextlite`).
* Route to EN/HE prompts in `answer_gen` and select HE snippets if present.
* Expand curated intent exemplars for HE; expose `?lang=` override for tests.

**Acceptance**

* Hebrew symptom prompt returns Hebrew advice when HE snippets exist.
* Intent routing robust for EN/HE mixed phrases.

---

## Small cross-cutting tasks you can slip into any PR

* **/debug endpoints**: `/api/debug/risk` returns scores & thresholds; `/api/debug/trace` dumps last node order and timings.
* **Citations dedupe:** you already added it—add a small unit test for `normalize_citation(...)`.
* **Seed service**: keep idempotent upserts; share HF cache volume.
* **Observability**: add request-id and per-node timing in the streamed events.

---

# Next PR Stack (Flexibility for Symptoms)

These PRs broaden symptom coverage beyond fixed phrases and improve relevance for queries like stomach pain without hardcoding per-case logic.

## PR 13 — Intent exemplars registry (+ multilingual)

Why: Make routing robust for new wordings in EN/HE.

Scope

- Add `docs/intent_exemplars.jsonl` (or `services/api/app/data/intent_exemplars.jsonl`) with bilingual examples per intent.
- Load via `INTENT_EXEMPLARS_PATH`; hot-reload in dev.
- Keep current embedding classifier but feed from the registry; make threshold/margin env-driven.

Acceptance

- New examples are picked up without code changes.
- Unit tests: Hebrew stomach-pain phrasing → `symptom`; restaurant queries → `other`.

Pointers

- `services/api/app/graph/nodes/supervisor.py` — replace `_DEFAULT_EXAMPLES`/`_EXEMPLARS` with file-backed loader and watch.

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

## PR 15 — Pattern-based fallback (safety templates)

Why: Provide minimal, safe guidance when retrieval returns nothing.

Scope

- Add a small, reviewed template set keyed by coarse symptom buckets (e.g., GI, respiratory, neuro), localized EN/HE.
- Trigger only when no snippets were found; always include disclaimers and escalation conditions.

Acceptance

- Unit tests assert GI queries yield a GI template when KB is empty; includes disclaimer and no diagnosis language.

Pointers

- `services/api/app/graph/nodes/answer_gen.py` — fallback builder consults template map before generic recap.

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
