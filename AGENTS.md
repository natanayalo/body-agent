# AGENTS.md — How to work in this repo

Scope: These instructions apply to the whole repository. They are for AI coding agents (and humans) working in this codebase so changes are consistent, safe, and easy to review.

## Mission & Priorities

- Privacy-first: never surface raw PII beyond the scrubber boundary. Prefer redacted `user_query_redacted` when possible.
- Ship in small, well-scoped increments aligned with `project/roadmap.md` (phases) and `project/roadmap/pr-stack.md`.
- Keep solutions simple, focused, and testable. Don’t fix unrelated issues.

## Repo Map (essentials)

- `services/api/app/graph/nodes/` — pipeline nodes (supervisor, scrub, memory, health, risk_ml, places, planner, answer_gen, critic).
- `services/api/app/graph/build.py` — LangGraph wiring and routing.
- `services/api/app/tools/` — shared utilities (embeddings, ES client, crypto, language, etc.).
- `project/` — product docs: roadmap (`project/roadmap.md`, `project/roadmap/pr-stack.md`, `project/roadmap/ideas.md`), direction (`project/vision.md`, `project/architecture.md`), and runbooks (`project/config.md`, `project/evaluation.md`, `project/privacy.md`, `project/troubleshooting.md`).
- `seeds/` — seed KB and providers. E2E tests rely on this content.
- `docker-compose.yml` — local dev stack; note mounted volumes.

## Planning Protocol

- Before doing multi-step work, create/maintain a short plan (5–7 words per step). Keep exactly one step in_progress. Update as you go.
- Use small, incremental changes tied to the “Next PR Stack” in `project/roadmap/pr-stack.md` (phase context lives in `project/roadmap.md`).
- Add or refine acceptance criteria within `project/roadmap/pr-stack.md` for new work; reflect backlog items in `project/roadmap/ideas.md`.

## Execution Guardrails

- Editing files: use patch-based edits; keep diffs surgical. Avoid broad refactors unless explicitly requested.
- Tests must pass. Coverage requirement is enforced at 95% (see `pytest.ini`).
- Prefer touching existing patterns and modules rather than inventing new structure.
- When adding config, wire via env vars and update `.env.example` and README.
- Avoid adding dependencies unless necessary; if you must, ensure tests and CI still pass.

## Running & Testing

- PYTHONPATH for local runs: `PYTHONPATH=services/api`.
- Unit + integration tests with coverage (95% gate):
  - `venv/bin/pytest` (uses root `pytest.ini`).
- Golden tests (quick eval):
  - `make eval`
- E2E tests (local ES + API in stub mode):
  - `make e2e-local` (or run targets individually: `e2e-local-up`, `e2e-local-api`, `e2e-local-wait`, `e2e-local-test`).
- Exemplars file: the app reads `INTENT_EXEMPLARS_PATH` (defaults to `/app/data/intent_exemplars.jsonl`). Ensure `data/intent_exemplars.jsonl` exists, or generate a new one and point the env var to it.

## Before You Commit (required)

- Run pre-commit on all files:
  - `pre-commit install` (first time only)
  - `pre-commit run --all-files`
- Run tests locally and meet coverage ≥ 95%:
  - `venv/bin/pytest` (unit + integration)
  - Optionally: `make eval` and `make e2e-local` if your change touches retrieval/routing/graph wiring.
- If you added config/env vars, update `.env.example`, `README.md`, and `project/config.md`.
- Keep diffs minimal and aligned with `project/roadmap/pr-stack.md` acceptance criteria.
- If scope/milestones changed, update `project/roadmap.md` and ensure `project/roadmap/pr-stack.md` reflects the current slices.
- Verify the shipping checklist in `project/SHIPPING.md` (demo steps, tests, docs) and ensure the PR template is complete.

## Key Env/Feature Flags

- `INTENT_EXEMPLARS_PATH` (JSON/JSONL): exemplar registry for the supervisor (defaults to `/app/data/intent_exemplars.jsonl`); enable `INTENT_EXEMPLARS_WATCH=true` to hot-reload.
- `LLM_PROVIDER` (`ollama|openai|none`), `OLLAMA_MODEL`, `OPENAI_API_KEY`.
- `RISK_MODEL_ID`, `RISK_THRESHOLDS`, `RISK_HYPOTHESIS`.
- ES indices: `ES_PRIVATE_INDEX`, `ES_PUBLIC_INDEX`, `ES_PLACES_INDEX`.

## Patterns to Follow

- Routing: The supervisor uses an embedding exemplar classifier with threshold+margin; prefer data-driven updates over code changes (edit exemplars).
- Retrieval: Keep queries PII-safe; adjust boosts and expansions in `health.py` per plan tasks.
- Answer generation: include citations, disclaimers, and risk-aware notices; avoid diagnosis and dosing.

## Safety & Privacy

- Do not log raw user text beyond what is already redacted by `scrub`.
- When adding new outputs, ensure no PII leakage. Cite sources for medical text.

## Adding New Work

- If the task is already listed in `project/roadmap/pr-stack.md`, follow its scope and acceptance criteria.
- Otherwise:
  - Propose an entry under “Scheduled” in `project/roadmap/ideas.md`.
  - If ready to execute, add a new PR block in `project/roadmap/pr-stack.md` with Why/Scope/Acceptance/Pointers.

## Communication (for agents)

- Before running grouped commands, send a brief preamble describing the next action.
- Keep progress updates short; mark plan steps as completed/in_progress appropriately.
- In final messages, summarize what changed and point to files and lines (e.g., `services/api/app/graph/build.py:45`).

## Do/Don’t Quicklist

- Do: keep diffs minimal, align with plan, maintain tests/coverage, document new env.
- Don’t: introduce unrelated refactors, leak PII, add dosing guidance, or bypass acceptance criteria.
