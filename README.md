# Body Agent (MVP)

Privacy-first personal health & life copilot. LangGraph-style orchestration, Elasticsearch RAG, local-first.

## Features

- **Privacy First**: Runs locally, with optional LLM provider integration.
- **Health Tracking**: Helps you remember your medications and symptoms.
- **Provider Search**: Finds healthcare providers near you.
- **Extensible**: Built with a modular LangGraph-based architecture.

## Getting Started


### Prerequisites

- Docker + Docker Compose
- ~2.5 GB free disk (Elasticsearch + model cache)

### Installation and Setup

1. **Clone the repository:**
   ```bash
   git clone <this-repo>
   cd body-agent
   ```

2. **Set up environment variables:**
   ```bash
   cp .env.example .env
   ```
   Update the `.env` file with your desired settings.

3. **Build and run the services:**
   ```bash
   docker compose up --build -d
   ```
   Wait ~10–20s for Elasticsearch and the API to be ready.

4. **Ingest initial data:**
   The following scripts will populate the Elasticsearch indices with public health information and local provider data.

   ```bash
   docker compose exec api python scripts/es_bootstrap.py
   docker compose exec api python scripts/ingest_public_kb.py
   docker compose exec api python scripts/ingest_providers.py

   ```

## Usage

The API is now available at `http://localhost:8000`. You can interact with it through the `/api/graph/run` endpoint.

### Example

To ask a question, send a POST request to `/api/graph/run`:

```bash
curl -X POST "http://localhost:8000/api/graph/run" -H "Content-Type: application/json" -d '''
{
  "user_id": "demo-user",
  "query": "I have a headache, what can I take?"
}
'''
```

## Development

### Running the linters

To run the linters, use the following command:

```bash

docker compose exec api ruff check .
```

### File Structure

```
body-agent/
├── README.md
├── docker-compose.yml
├── .env.example
├── services/
│ └── api/
│ ├── Dockerfile
│ ├── requirements.txt
│ └── app/
│ ├── main.py
│ ├── config.py
│ ├── graph/
│ │ ├── build.py
│ │ ├── state.py
│ │ └── nodes/
│ │ ├── supervisor.py
│ │ ├── memory.py
│ │ ├── health.py
│ │ ├── places.py
│ │ ├── planner.py
│ │ └── critic.py
│ └── tools/
│ ├── es_client.py
│ ├── embeddings.py
│ ├── calendar_tools.py
│ └── geo_tools.py
├── scripts/
│ ├── es_bootstrap.py
│ ├── ingest_public_kb.py
│ └── ingest_providers.py
└── seeds/
├── public_medical_kb/
│ ├── ibuprofen.md
│ ├── warfarin.md
│ └── fever_home_care.md
└── providers/
└── tel_aviv_providers.json
```