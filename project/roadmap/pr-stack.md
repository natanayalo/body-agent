Here’s a crisp next-step plan you can ship as a sequence of small PRs, each with concrete acceptance criteria and code pointers.

---

Refer to `project/roadmap/shipped.md` for completed slices.

# Milestone 3 — Stability & CI polish

## PR 27 — Seed container idempotent + stub-aware

- Ensure ingest scripts produce non-zero stub vectors, upsert by ID, and can rerun safely (especially in CI).
- Smoke validation via existing E2E suite.

## PR 29 — Docs: architecture/config/evaluation roll-up

- Publish the drafted docs (`docs/architecture.md`, `docs/config.md`, `docs/evaluation.md`) and link from README.

---

# Milestone 4 — Intent + privacy hardening

## PR 30 — Intent exemplar refresh + hot reload polish

- Ensure `INTENT_EXEMPLARS_PATH` watcher works end-to-end; add unit coverage for loader.

## PR 31 — PII scrub expansion

- Extend scrubber regexes for gov IDs and address fragments; redact to `[gov_id]` / `[address]`; cover with unit tests.
