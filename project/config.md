# Configuration & Modes

This page lists the key environment variables, defaults, and how to run in CI (stub) vs. local (real) modes.

## Core

- `APP_ENV` (dev|ci|test|prod)
- `HOST`, `PORT` (API bind)
- `APP_DATA_DIR` (default `/data` inside containers)
- `APP_LOG_DIR` (default `/logs`)

## Elasticsearch

- `ES_HOST` (e.g., `http://localhost:9200`)
- `ES_PRIVATE_INDEX` (default `private_user_memory`)
- `ES_PUBLIC_INDEX` (default `public_medical_kb`)
- `ES_PLACES_INDEX` (default `providers_places`)

## Embeddings & LLM

- `EMBEDDINGS_MODEL` (e.g., `sentence-transformers/all-MiniLM-L6-v2`)
- `EMBEDDINGS_DEVICE` (`cpu`|`cuda`)
- `LLM_PROVIDER` (`ollama|openai|none`)
- `OLLAMA_MODEL`, `OLLAMA_HOST`
- `OPENAI_API_KEY` (set to enable OpenAI)

## Risk classification

- `RISK_MODEL_ID` (e.g., `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli` or `__stub__`)
- `RISK_LABELS` (`urgent_care,see_doctor,self_care,info_only`)
- `RISK_THRESHOLDS` (e.g., `urgent_care:0.55,see_doctor:0.50`)
- `RISK_HYPOTHESIS` (template used for NLI predictions)
- `RISK_ONSET_RED_FLAGS` (comma-separated phrases—list each variant explicitly—that must always trigger ML checks for meds onset)

## Intent routing (exemplars)

- `INTENT_EXEMPLARS_PATH` (default `/app/data/intent_exemplars.jsonl`)
- `INTENT_EXEMPLARS_WATCH` (`true|false`)
- `INTENT_THRESHOLD` (default `0.30`)
- `INTENT_MARGIN` (default `0.05`)
- `INTENT_LANGS` (default `en,he`)

## Symptom registry (doc routing)

- `SYMPTOM_REGISTRY_PATH` (default `/app/registry/symptoms.yml`)

## Fallback templates (pattern-based)

- `FALLBACK_TEMPLATES_PATH` (optional; default unset; example `/app/data/safety_templates.json`)
- `FALLBACK_TEMPLATES_WATCH` (`true|false`)

## Deterministic meds onset

- `MED_FACTS_PATH` (default `/app/seeds/med_facts.json`)
- `PARAPHRASE_ONSET` (`true|false`, default `false`; paraphrase deterministic onset copy via Ollama with numeric validation)
- `ONSET_LLM_FALLBACK` (`true|false`, default `false`; LLM fallback that emits neutral, number-free guidance when no fact exists)

## Modes

### CI mode (deterministic)

- `EMBEDDINGS_MODEL=__stub__`
- `RISK_MODEL_ID=__stub__`
- `LLM_PROVIDER=none`
- CI copies curated seeds into `/app/data` and runs E2E with seeded ES.

### Local dev (real models)

- Choose actual `EMBEDDINGS_MODEL` and `RISK_MODEL_ID`.
- `LLM_PROVIDER=ollama` (recommended) or `openai` with API key.
- Keep exemplars/templates in `/app/data` for hot-reload.
