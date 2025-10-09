Here’s a crisp next-step plan you can ship as a sequence of small PRs, each with concrete acceptance criteria and code pointers.

---

Refer to `project/roadmap/shipped.md` for completed slices.

> **Legend:** `owner:` GitHub handle · `status:` TODO | IN-PROGRESS | REVIEW | SHIPPED

# Milestone 3 — Stability & CI polish

---

# Milestone 5 — Advanced planner features

## PR 37 — Preference-aware provider scoring

Why: Balance semantic relevance with distance, hours, and insurance so top candidates align with user priorities.

**owner:** @natanayalo
**status:** IN-PROGRESS
**rollback/flag:** set `PREFERENCE_SCORING_WEIGHTS=semantic:1.0,distance:0.0,hours:0.0,insurance:0.0`

**Scope**

- Introduce configurable weights for semantic, distance, hours, and insurance components (settings/env).
- Extend provider metadata/fixtures to expose insurance participation for ranking.
- Update ranking to apply weighted scoring while keeping rationale strings consistent with contributing factors.
- Teach planner rationales to mention insurance match once weighting is in place.

**Acceptance**

- Unit tests cover weighted scoring permutations (distance-heavy, insurance-heavy, default mix).
- Golden or integration test shows insurance-matched provider outranks mismatch when weights favor insurance.
- Planner rationales surface insurance match language when reason codes indicate coverage.
- Coverage stays ≥95% overall and ≥90% per file.
- **Kill if:** Weighted configuration still produces worse top-match click-through or increases latency >10% after two tuning passes.
  - (If killed, document rationale in ideas.md and revert weighting config to baseline default.)

**Pointers**

- `services/api/app/graph/nodes/places.py`, `services/api/tests/unit/test_places.py`, `seeds/providers/`, `project/config.md`, `.env.example`.

**Demo:**
```bash
curl -s http://localhost:8000/api/graph/run \
  -H 'content-type: application/json' \
  -d '{"user_id":"demo","query":"Find an endocrinologist","preferences":{"insurance_plan":"maccabi","max_travel_km":10}}' \
  | jq '.state.candidates | map({name, score, reasons})'
```

> **Numbering policy:** Section titles (e.g., “PR 36/37”) indicate planned order only. Actual PR numbers are assigned by GitHub once opened.
