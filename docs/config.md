# Configuration Guide

This guide centralises runtime knobs, defaults, and recommended settings for local development, CI, and production-like deployments. Mirror updates into `.env.example` whenever you introduce new variables.

## Core Application Settings

| Variable           | Default | Description |
|--------------------|---------|-------------|
| `APP_ENV`          | `dev`   | Execution mode (`dev`, `ci`, `test`, `prod`). Influences logging verbosity and stub usage. |
| `HOST` / `PORT`    | `0.0.0.0` / `8000` | Bind address for the FastAPI server. |
| `APP_DATA_DIR`     | `/data` | Path where exemplar/templates seeds are mounted inside containers. |
| `APP_LOG_DIR`      | `/logs` | Directory for structured application logs. |
| `LOG_LEVEL`        | `INFO`  | Standard Python logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |

## Elasticsearch

| Variable             | Default               | Notes |
|----------------------|-----------------------|-------|
| `ES_HOST`            | `http://localhost:9200` | All indices live on the same cluster; override when running in Docker Compose. |
| `ES_PRIVATE_INDEX`   | `private_user_memory` | Stores encrypted per-user facts. |
| `ES_PUBLIC_INDEX`    | `public_medical_kb`   | Seeds contain vetted medical snippets. |
| `ES_PLACES_INDEX`    | `providers_places`    | Geocoded providers and hours. |

## Embeddings & Language Models

| Variable              | Default    | Description |
|-----------------------|------------|-------------|
| `EMBEDDINGS_MODEL`    | `__stub__` | Sentence-transformer identifier or stub. Use a real model locally (e.g., `sentence-transformers/all-MiniLM-L6-v2`). |
| `EMBEDDINGS_DEVICE`   | `cpu`      | Set to `cuda` to leverage GPU acceleration. |
| `LLM_PROVIDER`        | `none`     | `none`, `ollama`, or `openai`. Controls whether answer generation invokes an LLM. |
| `OLLAMA_MODEL`        | `llama3` | Model served by the local Ollama instance. Only read when `LLM_PROVIDER=ollama`. |
| `OLLAMA_HOST`         | `http://localhost:11434` | Target Ollama endpoint. |
| `OPENAI_API_KEY`      | _unset_    | Required when `LLM_PROVIDER=openai`. Keep it out of version control. |

## Risk Classification

| Variable            | Default                                 | Usage |
|---------------------|-----------------------------------------|-------|
| `RISK_MODEL_ID`     | `__stub__`                              | Hugging Face model id or stub sentinel. |
| `RISK_LABELS`       | `urgent_care,see_doctor,self_care,info_only` | Expected label ordering for classifiers. |
| `RISK_THRESHOLDS`   | `urgent_care:0.55,see_doctor:0.50`      | Comma-delimited map of label → probability threshold. |
| `RISK_HYPOTHESIS`   | Domain-specific NLI prompt used by the classifier. |
| `RISK_ONSET_RED_FLAGS` | (unset)                             | Comma-delimited phrases that must always trigger ML evaluation even when heuristics would short-circuit. |

## Intent Routing & Templates

| Variable                 | Default                          | Description |
|--------------------------|----------------------------------|-------------|
| `INTENT_EXEMPLARS_PATH`  | `/app/data/intent_exemplars.jsonl` | File containing exemplar registry. |
| `INTENT_EXEMPLARS_WATCH` | `false`                          | Enable to hot-reload exemplars on change (dev only). |
| `INTENT_THRESHOLD`       | `0.30`                           | Minimum cosine similarity for a winning intent. |
| `INTENT_MARGIN`          | `0.05`                           | Required gap between first and second candidates. |
| `INTENT_LANGS`           | `en,he`                          | Languages that the exemplar registry supports. |
| `SYMPTOM_REGISTRY_PATH`  | `/app/registry/symptoms.yml`     | Canonical symptom definitions and doc pointers. |
| `FALLBACK_TEMPLATES_PATH`| _unset_                          | Optional JSON file with safety templates (EN/HE). |
| `FALLBACK_TEMPLATES_WATCH` | `false`                        | Hot-reload pattern templates in development. |

## Deterministic Meds Onset

| Variable             | Default                     | Description |
|----------------------|-----------------------------|-------------|
| `MED_FACTS_PATH`     | `/app/seeds/med_facts.json` | Seeded fact registry for vetted onset windows. |
| `PARAPHRASE_ONSET`   | `false`                     | When true, calls Ollama to paraphrase deterministic onset copy while enforcing numeric invariants. |
| `ONSET_LLM_FALLBACK` | `false`                     | Enables a number-free LLM blurb when no onset fact exists. |

## Mode Profiles

### CI Mode (deterministic)

Used in GitHub Actions and local `make e2e-local` runs when reproducibility matters.

```
APP_ENV=ci
EMBEDDINGS_MODEL=__stub__
RISK_MODEL_ID=__stub__
LLM_PROVIDER=none
PARAPHRASE_ONSET=false
ONSET_LLM_FALLBACK=false
```

The `seed` container populates Elasticsearch with stub embeddings and deterministic vectors. Re-running the ingest scripts is idempotent (see `docs/evaluation.md#seed-resets`).

### Local Development (full models)

```
APP_ENV=dev
EMBEDDINGS_MODEL=sentence-transformers/all-MiniLM-L6-v2
RISK_MODEL_ID=MoritzLaurer/mDeBERTa-v3-base-mnli-xnli
LLM_PROVIDER=ollama
OLLAMA_MODEL=openhermes
PARAPHRASE_ONSET=true
ONSET_LLM_FALLBACK=true
```

Feel free to tweak embedding/LLM identifiers according to GPU availability. Keep exemplar and template files inside `APP_DATA_DIR` to leverage hot reloaders.

### Production Preview

`APP_ENV=prod` currently behaves like `dev` but should be configured with:

- Hardened secrets (via Docker secrets or your orchestrator).
- Remote Elasticsearch cluster endpoints.
- LLM provider credentials fetched from a secret store instead of environment variables committed to disk.

Document any additional production-only knobs alongside runbooks in `project/config.md`.

## Observability

- `X-Request-ID` header: Clients may supply a request identifier per call. The API will normalize UUIDs and propagate the value through `state.debug.request_id` and include it on every SSE event. If omitted, the API generates a UUIDv4. Logs include `rid=<id>` to correlate runs and streams.
- `OUTBOUND_ALLOWLIST`: Comma-separated list of domains that outbound HTTP calls may reach (matches subdomains). Leave empty to allow any domain. The new `safe_request` / `safe_get` helpers in `app.tools.http` enforce this list and raise `OutboundDomainError` when a URL is not permitted.
