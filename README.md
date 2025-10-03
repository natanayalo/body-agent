# Body Agent (MVP)

Privacy-first personal health & life copilot. LangGraph-style orchestration, Elasticsearch RAG, local-first.

## How it works

The Body Agent is a multi-agent system orchestrated by LangGraph. It uses a local-first RAG architecture with Elasticsearch to provide a private and secure experience.

1.  **Input**: The user submits a query (e.g., "I have a headache, what can I take?").
2.  **Supervisor**: A supervisor agent analyzes the query and determines the user's intent.
3.  **Memory**: The system retrieves relevant information from your personal knowledge base (e.g., medications, allergies).
4.  **RAG**: The query is enriched with this information and sent to the appropriate specialist agent (e.g., Health, Places).
5.  **Planner & Critic**: A planner agent creates a course of action, which is then reviewed by a critic agent.
6.  **Output**: The final response is presented to the user.

## Features

- **Privacy First**: Runs locally, with optional LLM provider integration.
- **Health Tracking**: Helps you remember your medications and symptoms.
- **Provider Search**: Finds healthcare providers near you.
- **Personalized Ranking**: Provider results respect saved preferences (distance, kind, hours).
- **Safety-First Answers**: Optional LLM node summarises findings with citations and disclaimers.
- **Extensible**: Built with a modular LangGraph-based architecture.
- **Streaming API**: Real-time, node-by-node event streaming for a responsive UX.
- **Encryption at Rest**: Per-user key encryption for private memory values.

## Documentation

- [Architecture](docs/architecture.md) — Graph topology, node responsibilities, and streaming contract.
- [Configuration](docs/config.md) — Environment variables and mode profiles for dev, CI, and prod.
- [Evaluation](docs/evaluation.md) — Test matrix, coverage gates, and QA checklist.

## Getting Started

1.  **Prerequisites:**
    -   Docker + Docker Compose
    -   ~2.5 GB free disk (Elasticsearch + model cache)

2.  **Clone the repository:**

    ```bash
    git clone <this-repo>
    cd body-agent
    ```

3.  **Set up environment variables:**

    ```bash
    cp .env.example .env
    ```

    Update the `.env` file with your desired settings.

4.  **Build and run the services:**

    ```bash
    docker compose up --build -d
    ```

    Wait ~10–20s for Elasticsearch and the API to be ready.

5.  **Ingest initial data:**

    The `seed` container now automatically populates the Elasticsearch indices with public health information and local provider data when you run `docker compose up`. You no longer need to run these scripts manually.

## Usage

The API is now available at `http://localhost:8000`. You can interact with it through the `/api/graph/run` and `/api/graph/stream` endpoints.

### Examples

**Symptom check (batch):**

```bash
curl -X POST "http://localhost:8000/api/graph/run" -H "Content-Type: application/json" -d '''
{
  "user_id": "demo-user",
  "query": "I have a headache, what can I take?"
}
'''
```

**Symptom check (streaming):**

```bash
curl --no-buffer -X POST "http://localhost:8000/api/graph/stream" -H "Content-Type: application/json" -d '''
{
  "user_id": "demo-user",
  "query": "I have a headache, what can I take?"
}
'''
```

Server-Sent Events (SSE) format (final is last):

```
data: {"node":"memory","delta":{"memory_facts":[...]}}

data: {"node":"health","delta":{"public_snippets":[...]}}

data: {"node":"risk_ml","delta":{"debug":{"scores":{...},"triggered":[...]}}}

data: {"final":{"state":{...}}}
```

Note: `/api/graph/run` returns a stable envelope: `{ "state": { ... } }`.

**Find a provider:**

```bash
curl -X POST "http://localhost:8000/api/graph/run" -H "Content-Type: application/json" -d '''
{
  "user_id": "demo-user",
  "query": "Find a lab near me for a blood test."
}
'''


## Optional: Better intent routing with exemplars

By default the supervisor uses an **embedding-based** router. The repo ships a curated EN/HE exemplar set under `seeds/intent_exemplars.jsonl`, while the app reads from `INTENT_EXEMPLARS_PATH` (default `/app/data/intent_exemplars.jsonl`). Copy the curated file into your data volume or point the env var directly to your generated file. Hot-reload is available with `INTENT_EXEMPLARS_WATCH=true`.

If you want to regenerate or extend the exemplars using the **MASSIVE** dataset:

```bash
# internet required on first run
docker compose exec api python scripts/build_intent_exemplars.py \
  --langs en he --per-intent 40 --out /app/data/intent_exemplars.json
```

Then update `INTENT_EXEMPLARS_PATH` in `.env` to point at your generated file (for example `/app/data/intent_exemplars.json`) and restart the API container.

Config knobs (in `.env`):

```
INTENT_THRESHOLD=0.30   # min cosine for top intent
INTENT_MARGIN=0.05      # top - second must exceed this
FALLBACK_TEMPLATES_PATH=/app/data/safety_templates.json  # optional file-backed symptom templates (EN/HE); see seeds/safety_templates.json
FALLBACK_TEMPLATES_WATCH=false                           # enable hot-reload in dev
SYMPTOM_REGISTRY_PATH=/app/registry/symptoms.yml         # maps canonical symptoms to doc IDs + expansions
```

Notes:
- We currently map only obvious MASSIVE labels to our buckets (`appointment`, `routine`). Health-specific intents (`symptom`, `meds`) are curated in the script.
- The supervisor precomputes embeddings for exemplars at import time for speed.
- Fallback answer generation includes pattern-based, file-backed templates for common symptom buckets; when a provider is disabled/unavailable and retrieval returns nothing, a safe, non-dosing template is used.


## Development


### Tests & Coverage

Run the test suite locally before committing. CI enforces an overall coverage floor of **95%** and at least **90% per file**.

```bash
venv/bin/pytest --cov --cov-report=term-missing
```

If any file drops below the threshold, pytest will exit non‑zero—fix the coverage locally so the CI job stays green.

### Pre-commit Hooks

This project uses pre-commit to enforce code style and quality. To use it, you need to have pre-commit installed on your system.

1.  **Install pre-commit:**

    ```bash
    pip install pre-commit
    ```

2.  **Install the git hooks:**

    ```bash
    pre-commit install
    ```

Now, the pre-commit hooks will run automatically every time you make a commit. You can also run them manually on all files:

```bash
pre-commit run --all-files
```

### Running the linters

To run the linters, use the following command:

```bash
docker compose exec api ruff check .
```

### Logging

The application uses Python's standard `logging` module. Log levels can be controlled via the `LOG_LEVEL` environment variable (e.g., `INFO`, `DEBUG`, `WARNING`, `ERROR`). Logs are output to both console and a file (`/var/log/body-agent/api.log` by default).


### Risk & Embedding Models Stubbing

For testing and CI environments, the large language model used for risk classification can be replaced with a lightweight stub. This avoids the need to download the full model, speeding up test runs and reducing resource consumption.

To enable the stub, set the `RISK_MODEL_ID` and `EMBEDDINGS_MODEL` environment variable to `__stub__`:

```bash
RISK_MODEL_ID=__stub__
EMBEDDINGS_MODEL=__stub__
```

When stubbing is active, the risk classification will return deterministic, default scores, allowing for predictable test outcomes.

To tweak the meds-onset gating, set `RISK_ONSET_RED_FLAGS` to a comma-separated list of phrases, listing each variant you care about (e.g., `RISK_ONSET_RED_FLAGS=chest pain,chest pains,bleed,bleeding`). Any query containing one of the phrases will always run through the ML risk model instead of being suppressed.

Deterministic onset answers can be lightly localized by enabling `PARAPHRASE_ONSET=true` (defaults to `false`). When enabled, the node calls the configured Ollama model to rewrite the fact copy while preserving every numeric value; if validation fails or Ollama is unreachable, the canonical wording is used.

If no vetted onset fact exists, turning on `ONSET_LLM_FALLBACK=true` (defaults to `false`) will ask the configured LLM for a short, neutral blurb that contains no numbers or dosing guidance. The validator rejects any output that introduces timings and falls back to the deterministic templates instead.


### Security & Tenancy (PR 8)

- Private memory values (e.g., the `value` field in `/api/memory/add_med`) are encrypted at rest using a per-user Fernet key.
- Keys are stored under `${APP_DATA_DIR}/keys/<user_id>.key` and created on first use.
- Indexed docs include `value_encrypted: true` and the ciphertext in `value`.
- For debugging, decrypt via `app.tools.crypto.decrypt_for_user(user_id, token)` from a Python shell (local only).


### Local E2E Runner (CI Parity)

Run the full E2E flow locally with the same steps as CI (fresh ES, stub models, seeded data, API startup):

```
make e2e-local
```

Useful sub-steps:

- `make e2e-local-up` — start ES, ensure indices, seed (stub embeddings)
- `make e2e-local-api` — start API (stub mode) in background
- `make e2e-local-wait` — wait until `/healthz` is ready
- `make e2e-local-test` — run the E2E tests
- `make e2e-local-logs` — tail `/tmp/api.log`
- `make e2e-local-down` — stop containers (volumes removed)
- `make e2e-local-clean` — delete ES indices to reseed cleanly

### Evaluation Harness (Golden Tests)

Run a deterministic regression suite against curated prompts:

```
make eval
```

The golden tests call `/api/graph/run` with English and Hebrew scenarios, assert intent/risk behavior, and verify citations stay deduplicated.

### API Explorer

Visit `http://localhost:8000/docs` for an interactive Scalar UI in dark mode. Every operation has “Try It” enabled, so you can exercise the graph directly from the browser without managing a custom Swagger theme.

### LLM Configuration

Set `LLM_PROVIDER=ollama` (default `none`) to enable the answer generation node. When enabled, the graph invokes the provider after planning to craft a cited response.
- `OLLAMA_MODEL` (default `llama3`) selects the local model served by Ollama.
- `OPENAI_API_KEY`/`OPENAI_MODEL` are used if you set `LLM_PROVIDER=openai`.
If no provider is configured, the node is skipped and the pipeline behaves as before.

The API auto-detects the user query language (English or Hebrew). You can override detection by adding `lang=en`/`lang=he` to requests. The answer generator uses localized prompts/disclaimers and will prefer snippets that match the selected language, falling back to the remaining sources when needed.

### Debugging Aids

Two helper endpoints expose the most recent run metadata:

- `/api/debug/trace` – returns the ordered list of graph nodes with per-node execution time (milliseconds) and the ISO timestamp for the latest run.
- `/api/debug/risk` – surfaces the last ML risk classification payload along with the configured labels and thresholds.

These are handy when tuning routing or adjusting risk thresholds in development.

Install the matching SDK so the node can import it. The API requirements include both
`ollama` and `openai`; rebuild the container or reinstall the dependencies after pulling
this branch:

```
docker compose build api
# or, locally
pip install -r services/api/requirements.txt
```


### File Structure

```
body-agent/
├── README.md
├── docker-compose.yml
├── .env.example
├── services/
│   └── api/
│       ├── Dockerfile
│       ├── requirements.txt
│       └── app/
│           ├── main.py
│           ├── config/
│           │   ├── __init__.py
│           │   ├── logging.py
│           │   └── settings.py
│           ├── data/
│           ├── graph/
│           │   ├── build.py
│           │   ├── state.py
│           │   └── nodes/
│           │       ├── supervisor.py
│           │       ├── memory.py
│           │       ├── health.py
│           │       ├── places.py
│           │       ├── planner.py
│           │       ├── critic.py
│           │       └── risk_ml.py
│           └── tools/
│               ├── es_client.py
│               ├── embeddings.py
│               ├── calendar_tools.py
│               ├── geo_tools.py
│               └── crypto.py
├── Makefile
├── scripts/
│   ├── build_intent_exemplars.py
│   ├── es_bootstrap.py
│   ├── ingest_public_kb.py
│   ├── ingest_providers.py
│   └── wait_for_es.py
├── data/
│   └── calendar_events/
└── seeds/
    ├── public_medical_kb/
    │   ├── ibuprofen.md
    │   ├── warfarin.md
    │   └── fever_home_care.md
    └── providers/
        └── tel_aviv_providers.json
```
