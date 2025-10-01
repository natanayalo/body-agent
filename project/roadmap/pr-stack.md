Here’s a crisp next-step plan you can ship as a sequence of small PRs, each with concrete acceptance criteria and code pointers.

---

Refer to `project/roadmap/shipped.md` for completed slices.

# Next PR Stack — Milestone 2 (optional onset polish)

With the meds onset core shipped, focus now shifts to the opt-in polish flags for deterministic answers.

## PR 25 — Paraphrase onset facts via Ollama (flagged)

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

## PR 26 — LLM neutral fallback for onset (no fact; flagged)

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
