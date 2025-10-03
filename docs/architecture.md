# Architecture

This document captures the end-to-end layout of the Body Agent stack so new contributors can quickly reason about control flow, storage, and external dependencies. For a condensed checklist of the current milestone focus, see `project/architecture.md`.

## Runtime Overview

The runtime is a LangGraph-powered FastAPI service that streams node outputs over Server-Sent Events (SSE). Each user query flows through a deterministic graph of nodes:

```
scrub → supervisor → memory → { health | places } → risk_ml → planner → answer_gen → critic → final
```

- **scrub** — removes personally identifiable information (PII) and annotates the language before anything touches logging or downstream nodes.
- **supervisor** — embeds the redacted query and routes to the correct intent/sub-intent using exemplar classifiers (EN/HE by default).
- **memory** — fetches private, per-user context (meds, allergies, preferences) from Elasticsearch (`private_user_memory`). Secrets are encrypted at rest using the per-user key service.
- **health** — retrieves public medical guidance from Elasticsearch (`public_medical_kb`) with a hybrid kNN + BM25 strategy, boosted by the symptom registry.
- **places** — looks up providers/locations in Elasticsearch (`providers_places`) and applies deterministic ranking using stored preferences.
- **risk_ml** — runs the risk classifier (either real NLI model or `__stub__`) and flags red/amber cases.
- **planner** — builds structured plans (appointments, follow-ups, or no-op) and carries forward observability breadcrumbs.
- **answer_gen** — renders deterministic recaps, optionally calls an LLM (Ollama/OpenAI) behind feature flags, and always attaches citations/disclaimers.
- **critic** — enforces safety contracts: citations present, disclaimers intact, language matches, and no dosing claims slip through.

The graph is strictly ordered for streaming. Nodes that are not part of the active branch (e.g., `places` when handling a pure meds-onset question) are skipped but the event order for emitted nodes is invariant.

## API Surface

- `POST /api/graph/run` — Executes the full graph and responds with `{ "state": { ... } }` once the final state is available.
- `POST /api/graph/stream` — Streams graph progress as SSE chunks. Each chunk begins with `data:` and contains JSON. The terminal message always includes a `final` payload with the exact serialized state returned by `/api/graph/run`.

### Streaming Contract

1. `content-type` must be `text/event-stream`.
2. At least one intermediate chunk contains a `delta` field indicating a node update.
3. The last chunk **must** include `{"final": {"state": …}}` and no further messages follow.
4. Error scenarios surface an `{"error": {...}}` chunk so clients can surface meaningful failures without inspecting server logs.

## Data & Storage

| Index / Store            | Purpose                                   | Notes |
|--------------------------|-------------------------------------------|-------|
| `private_user_memory`    | User-specific meds, allergies, preferences| AES-GCM encrypted values; filtered by `user_id`. |
| `public_medical_kb`      | Medical snippets & guidance               | Hybrid kNN + BM25; language-filtered (`en`, `he`). |
| `providers_places`       | Providers, labs, and scheduling metadata  | Geo filters + preference weighting. |
| Seed JSON/YAML files     | Med facts, templates, symptom registry    | Mounted into containers; hot-reload supported where flagged. |

All indices are seeded via the `seed` container. CI runs in stub mode so ingest scripts can be executed repeatedly without leaving dangling data (see `docs/config.md#ci-mode`).

## External Services & Models

- **Elasticsearch** — Backing store for memory, public knowledge, and provider data. Required in all modes.
- **Embedding model** — Configurable via `EMBEDDINGS_MODEL`; defaults to `__stub__` in CI to avoid large downloads.
- **Risk model** — Controlled by `RISK_MODEL_ID`; also supports the `__stub__` mode.
- **LLM provider** — Optional. Set `LLM_PROVIDER=ollama` or `openai` to enable paraphrasing or fallback generation. When disabled, the system falls back to deterministic templates.

## Feature Flags & Deterministic Paths

Several flows are gated behind environment flags so we can ship incremental improvements safely:

- `PARAPHRASE_ONSET` — Calls Ollama to rephrase deterministic meds-onset facts while validating that numerics remain unchanged.
- `ONSET_LLM_FALLBACK` — Invokes an LLM when no vetted onset fact exists to produce a short, number-free neutral blurb.
- `INTENT_EXEMPLARS_WATCH` / `FALLBACK_TEMPLATES_WATCH` — Enable hot-reloading of exemplar and template files in development.

Feature flags always degrade gracefully to deterministic templates so CI and offline environments remain reliable.

## Observability Hooks

- **Structured logging** — All nodes emit structured log lines with `intent`, `user_id` (hashed), and timing information. PII is stripped at the scrubber boundary.
- **Graph debug payload** — The running state carries `debug` fields (e.g., `debug.risk.triggered`, `debug.health.retrieval`) to aid in integration tests and inspection via the SSE stream.
- **Coverage gates** — Pytest enforces ≥95% overall coverage and ≥90% per file, ensuring new code paths stay exercised.

## Extending the Graph

1. Add your node implementation under `services/api/app/graph/nodes/` and wire it into `services/api/app/graph/build.py`.
2. Update `project/roadmap/pr-stack.md` with scope/acceptance criteria for the new work.
3. Provide unit tests for business logic and, where relevant, extend integration tests to exercise the new node’s contract.
4. Document any new configuration or seeds. Environment variables belong in `.env.example`, `docs/config.md`, and supporting references in `project/config.md`.

Keeping these steps tight ensures future PRs stay small, testable, and aligned with the privacy-first charter.
