# Body Agent (MVP)

Privacy-first personal health & life copilot. LangGraph-style orchestration, Elasticsearch RAG, local-first.

## File tree

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
