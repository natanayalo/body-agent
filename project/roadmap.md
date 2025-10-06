# Roadmap (MVP → v1)

## Now — Milestone 2 (Optional meds onset polish)

- Paraphrase deterministic onset facts without changing numbers (PR 25, flagged)
- Neutral LLM fallback when no onset fact exists (PR 26, flagged)

## Next — Milestone 3 (Stability & CI polish)

- Idempotent seed job for ingest scripts (PR 27)
- SSE contract regression test (PR 28)
- Docs roll-up linking architecture/config/evaluation references (PR 29)

## Later — Milestone 4 (Intent + privacy hardening)

- Intent exemplar hot-reload refinements (PR 30)
- Expanded PII scrub rules for gov IDs and addresses (PR 31)
-- Longer-term: client-side field encryption, calendar integration, vetted MCP adapters

See `project/roadmap/pr-stack.md` for current PR slices and acceptance criteria. Completed work is archived in `project/roadmap/shipped.md`.

## On Deck — Milestone 5 (Observability & Safety connectors)

- Request ID propagation across logs/SSE for easy correlation (PR 32)
- Risk evaluation harness with golden prompts and CI check (PR 33)
- Outbound domain allow-list (fail-closed by default) (PR 34)
- Preference expansion: `max_travel_km` distance filter in planner (PR 35)
