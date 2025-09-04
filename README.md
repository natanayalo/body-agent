# Body Agent (MVP)

Privacy-first personal health & life copilot. LangGraph-style orchestration, Elasticsearch RAG, local-first.

## Overview

This project implements a privacy-focused health assistant that:
- Processes all data locally for maximum privacy
- Uses vector search for semantic understanding of medical information
- Maintains conversation context through a memory system
- Coordinates multiple specialized components through a graph architecture
- Provides health information and healthcare provider recommendations

## File tree

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
│ │ ├── __init__.py
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

## Prereqs
- Docker + Docker Compose
- ~2.5 GB free disk (Elasticsearch + model cache)

## Run
```bash
git clone <this-repo>
cd body-agent
cp .env.example .env
docker compose up --build -d
# wait ~10–20s for ES and API
```

## Important Notes

### Architecture
- Privacy-first design: All data processing happens locally
- LangGraph orchestration: Modular nodes handle specific tasks (health, memory, planning, etc.)
- Vector-based RAG: Uses Elasticsearch for semantic search of medical knowledge and providers
- Stateful conversations: Maintains context through the memory node

### Data Components
- Medical Knowledge Base: Public health information (medications, conditions, care instructions)
- Provider Directory: Healthcare facility locations with semantic search capabilities
- User Memory: Contextual storage for user-specific health information

### Usage Flow
1. API receives user query
2. Supervisor node orchestrates processing through specialized nodes
3. Health node retrieves relevant medical information
4. Places node finds healthcare providers if needed
5. Planner node handles scheduling and reminders
6. Memory node maintains conversation context
7. Critic node validates responses for safety

### API Endpoints
- POST `/api/run`: Main endpoint for user queries
  ```bash
  curl -X POST http://localhost:8000/api/run \
    -H 'Content-Type: application/json' \
    -d '{"user_id":"demo-user","query":"Can I take ibuprofen tonight with my meds?"}'
  ```

### Data Initialization
After starting the containers, run:
```bash
# Initialize medical knowledge base
docker compose exec api python scripts/ingest_public_kb.py
# Initialize healthcare providers
docker compose exec api python scripts/ingest_providers.py
```

### Limitations
- Medical information is for reference only
- Always consult healthcare professionals for medical advice
- Provider data is sample data for demonstration purposes
