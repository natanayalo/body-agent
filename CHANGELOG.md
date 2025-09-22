# Changelog

All notable changes to this project are documented here. Dates are in YYYY-MM-DD.

## 2025-09-21 — PR 13: Intent exemplars registry (multilingual)

- Feature: File-backed intent exemplars registry for the supervisor.
  - Supports JSON and JSONL via `INTENT_EXEMPLARS_PATH`.
  - Hot-reload in dev with `INTENT_EXEMPLARS_WATCH=true`.
  - Default path now `/app/data/intent_exemplars.jsonl` (mounted data volume).
- Tests: Added/updated unit tests to cover JSONL parsing, watch/reload, and Hebrew routing for stomach-pain queries.
- CI: Points env var to `data/intent_exemplars.jsonl` and ensures the data dir exists.
- Docs: Planning moved to `docs/roadmap/`; added `AGENTS.md`; clarified exemplar paths and local workflows.

## 2025-09-21 — PR 12: i18n & language detection

- Language detection and routing added.
  - Detects EN/HE and routes prompts/templates accordingly (`app/tools/language.py`).
  - Tests ensure mixed-language robustness.
- Debug endpoints and observability improvements (see below) landed around this time.

## 2025-09-19 — PR 11: LLM generation (local-first)

- Answer generation node added (`app/graph/nodes/answer_gen.py`).
  - Supports `LLM_PROVIDER=ollama|openai|none` with Ollama-first.
  - Inserts medical disclaimers; respects risk signals; cites sources.
  - Falls back gracefully when provider is `none`.

## 2025-09-18 — PR 10: Evaluation harness (golden set)

- Added golden test suite (`services/api/tests/golden/`).
  - Asserts intent classification, citations present, and risk signals under stubs.
  - `make eval` convenience target.

## 2025-09-16 — PR 9: Provider ranking + preferences

- Places node ranks providers deterministically with reasons (`app/graph/nodes/places.py`).
  - Honors simple preference hints (e.g., preferred kind) with tests (`test_places.py`).
  - Preps planner to include top candidate + ICS generation.

## 2025-09-15 — PR 8: Encryption & tenancy (field-level)

- Field-level encryption for private memory values (`app/tools/crypto.py`).
  - `add_med` stores encrypted `value` with `value_encrypted=true`.
  - Queries enforce `user_id` partitioning.

## 2025-09-12 — PR 7: StateGraph + streaming API

- Migrated from linear pipeline to LangGraph StateGraph (`app/graph/build.py`).
  - Conditional routing based on intent.
  - Added `/api/graph/stream` SSE endpoint emitting node-by-node deltas.

## 2025-09-11 — Utilities & endpoints (shipped alongside PRs)

- PII scrubber node filters sensitive text early (`app/graph/nodes/scrub.py`).
- Debug endpoints in API (`/api/debug/trace`, `/api/debug/risk`) for observability.
- ICS generator utilities (`app/tools/calendar_tools.py`) with sample events.
