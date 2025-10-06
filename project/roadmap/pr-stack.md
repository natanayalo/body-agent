Here’s a crisp next-step plan you can ship as a sequence of small PRs, each with concrete acceptance criteria and code pointers.

---

Refer to `project/roadmap/shipped.md` for completed slices.

# Milestone 3 — Stability & CI polish

---

# Milestone 4 — Intent + privacy hardening

---

# Milestone 5 — Observability & Safety connectors

## PR 32 — Request ID propagation (end-to-end)

Why: Correlate logs, SSE chunks, and traces per user request for faster debugging.

Scope

- Generate a UUIDv4 `request_id` at API entry; accept an incoming `X-Request-ID` header and normalize.
- Thread `request_id` through `state.debug.request_id` and include it in every SSE chunk.
- Add structured log fields `request_id`, `user_id_hash`, and elapsed timings.

Acceptance

- SSE events contain a stable `request_id` matching the non-streaming response.
- Logs include `request_id` for each node emission.
- Unit/integration tests assert presence and stability of the ID.

Pointers

- `services/api/app/main.py` (request hook), `services/api/app/graph/build.py` (state init), streaming tests in `services/api/tests/integration/test_streaming.py`.

## PR 33 — Risk eval harness (golden tests)

Why: Make risk threshold tuning safer with a reproducible prompt set.

Scope

- Add `make eval-risk` target invoking a small golden set (EN/HE) and printing per-label hit rates.
- Store fixtures under `seeds/evals/risk/*.jsonl` with provenance notes.
- Document how to add cases and interpret output.

Acceptance

- Running `make eval-risk` prints a summary and exits non-zero if any metric regresses beyond a configurable tolerance.
- CI job executes the target on PRs that touch `risk_ml.py`.

Pointers

- `services/api/app/graph/nodes/risk_ml.py`, `Makefile`, docs in `docs/evaluation.md`.

## PR 34 — Outbound domain allow-list (fail-closed)

Why: Ensure any future web connectors only talk to vetted domains by default.

Scope

- Add `OUTBOUND_ALLOWLIST` env (comma-separated domains); when set, block HTTP calls to non-allowed domains.
- Provide helper `safe_fetch(url)` that enforces the allow-list and is used by adapters.
- Add error surface that explains why a domain was blocked.

Acceptance

- Unit tests cover allowed/blocked domains, subdomain handling, and error messages.
- Default behavior in CI/dev is fail-closed unless explicitly configured.

Pointers

- `services/api/app/tools/http.py` (new), `.env.example`, tests in `services/api/tests/unit/test_http.py`, docs in `project/config.md`.

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
