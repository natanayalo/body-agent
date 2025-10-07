Here’s a crisp next-step plan you can ship as a sequence of small PRs, each with concrete acceptance criteria and code pointers.

---

Refer to `project/roadmap/shipped.md` for completed slices.

# Milestone 3 — Stability & CI polish

---

# Milestone 5 — Observability & Safety connectors

## PR 35 — Preference expansion (distance filter)

Why: Make planner results more personally relevant without adding complexity.

Scope

- Extend `private_user_memory` with `preferences.max_travel_km` and backfill seed fixtures.
- Filter provider candidates in `places` by distance ≤ `max_travel_km` before ranking; keep existing scoring.
- Expose the applied filter in planner reasons.

Acceptance

- Unit/integration tests set a short `max_travel_km` and assert farther providers are excluded.
- Planner reasons mention the distance filter when applied.

Pointers

- `services/api/app/graph/nodes/places.py`, `services/api/app/graph/nodes/planner.py`, seeds in `seeds/providers/`, tests in `services/api/tests/unit/test_places.py`.
