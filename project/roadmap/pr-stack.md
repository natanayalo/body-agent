Here’s a crisp next-step plan you can ship as a sequence of small PRs, each with concrete acceptance criteria and code pointers.

---

Refer to `project/roadmap/shipped.md` for completed slices.

> **Legend:** `owner:` GitHub handle · `status:` TODO | IN-PROGRESS | REVIEW | SHIPPED

# Milestone 3 — Stability & CI polish

---

# Milestone 5 — Advanced planner features

## PR 36 — Planner rationale templates

Why: Give users a concise explanation for why a suggested appointment slot fits their preferences.

**owner:** @natanayalo
**status:** TODO
**rollback/flag:** `PLANNER_RATIONALE_ENABLED=false`

Scope

- Add short EN/HE rationale strings that reference distance/availability data when present.
- Persist the rationale on the planner plan payload and surface it in responses (SSE + REST).
- Ensure rationales reuse scrubbed data and never echo raw PII.

Acceptance

- Unit tests cover rationale assembly for English and Hebrew planner flows (with/without preferences).
- Golden test validates the rationale appears alongside the selected provider in the appointment scenario.
- Existing planner acceptance checks remain green.

Pointers

- `services/api/app/graph/nodes/planner.py`, `services/api/app/graph/nodes/places.py`, `services/api/tests/unit/test_planner.py`, `services/api/tests/golden/inputs.jsonl`.

**Demo:**
```bash
curl -s http://localhost:8000/api/graph/run \
  -H 'content-type: application/json' \
  -d '{"user_id":"demo","query":"Please book a cardiology clinic tomorrow morning","preferences":{"max_travel_km":5}}' \
  | jq '.state.plan.explanations'
```

## PR 37 — Preference-aware provider scoring

Why: Balance semantic relevance with distance, hours, and insurance so top candidates align with user priorities.

**owner:** @natanayalo
**status:** TODO
**rollback/flag:** set `PREFERENCE_SCORING_WEIGHTS=semantic:1.0,distance:0.0,hours:0.0,insurance:0.0`

Scope

- Introduce configurable weights for semantic, distance, hours, and insurance components (settings/env).
- Extend provider metadata/fixtures to expose insurance participation for ranking.
- Update ranking to apply weighted scoring while keeping rationale strings consistent with contributing factors.
- Teach planner rationales to mention insurance match once weighting is in place.

Acceptance

- Unit tests cover weighted scoring permutations (distance-heavy, insurance-heavy, default mix).
- Golden or integration test shows insurance-matched provider outranks mismatch when weights favor insurance.
- Coverage stays ≥95% overall and ≥90% per file.

Pointers

- `services/api/app/graph/nodes/places.py`, `services/api/tests/unit/test_places.py`, `seeds/providers/`, `project/config.md`.

**Demo:**
```bash
curl -s http://localhost:8000/api/graph/run \
  -H 'content-type: application/json' \
  -d '{"user_id":"demo","query":"Find an endocrinologist","preferences":{"insurance_plan":"maccabi","max_travel_km":10}}' \
  | jq '.state.candidates | map({name, score, reasons})'
```

> **Numbering policy:** Section titles (e.g., “PR 36/37”) indicate planned order only. Actual PR numbers are assigned by GitHub once opened.
