# Changelog

All notable changes to this project are documented here. Dates are in YYYY-MM-DD.

## 2025-09-21 — PR 13: Intent exemplars registry (multilingual)

- Feature: File-backed intent exemplars registry for the supervisor.
  - Supports JSON and JSONL via `INTENT_EXEMPLARS_PATH`.
  - Hot-reload in dev with `INTENT_EXEMPLARS_WATCH=true`.
  - Default path now `/app/data/intent_exemplars.jsonl` (mounted data volume).
- Tests: Added/updated unit tests to cover JSONL parsing, watch/reload, and Hebrew routing for stomach-pain queries.
- CI: Copies curated exemplars into `data/intent_exemplars.jsonl` and points env var to it.
- Docs: Planning moved to `docs/roadmap/`; added `AGENTS.md`; clarified exemplar paths and local workflows.
