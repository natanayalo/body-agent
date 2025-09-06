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
- **Extensible**: Built with a modular LangGraph-based architecture.

## Getting Started

### Prerequisites

- Docker + Docker Compose
- ~2.5 GB free disk (Elasticsearch + model cache)

### Installation and Setup

1.  **Clone the repository:**

    ```bash
    git clone <this-repo>
    cd body-agent
    ```

2.  **Set up environment variables:**

    ```bash
    cp .env.example .env
    ```

    Update the `.env` file with your desired settings.

3.  **Build and run the services:**

    ```bash
    docker compose up --build -d
    ```

    Wait ~10–20s for Elasticsearch and the API to be ready.

4.  **Ingest initial data:**

    The following scripts will populate the Elasticsearch indices with public health information and local provider data.

    ```bash
    docker compose exec api python scripts/es_bootstrap.py
    docker compose exec api python scripts/ingest_public_kb.py
    docker compose exec api python scripts/ingest_providers.py
    ```

## Usage

The API is now available at `http://localhost:8000`. You can interact with it through the `/api/graph/run` endpoint.

### Examples

**Symptom check:**

```bash
curl -X POST "http://localhost:8000/api/graph/run" -H "Content-Type: application/json" -d '''
{
  "user_id": "demo-user",
  "query": "I have a headache, what can I take?"
}
'''
```

**Find a provider:**

```bash
curl -X POST "http://localhost:8000/api/graph/run" -H "Content-Type: application/json" -d '''
{
  "user_id": "demo-user",
  "query": "Find a lab near me for a blood test."
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
