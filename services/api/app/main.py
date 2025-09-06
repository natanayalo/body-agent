from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
from app.config import settings
from app.tools.es_client import ensure_indices
from app.graph.state import BodyState
from app.graph.build import build_graph
from app.tools.es_client import es
from app.tools.embeddings import embed
import re

# keep node imports available (legacy)
from app.graph.nodes import supervisor, memory, health, places, planner, critic

app = FastAPI(title="Body Agent API")

class Query(BaseModel):
    user_id: str = "demo-user"
    query: str

@app.on_event("startup")
async def startup():
    ensure_indices()
    app.state.graph = build_graph().compile()

def _invoke_graph(user_id: str, text: str) -> BodyState:
    state: BodyState = {
        "user_id": user_id,
        "user_query": text,
        "messages": []
    }
    return app.state.graph.invoke(state)

@app.post("/api/graph/run")
def run_graph(q: Query):
    return _invoke_graph(q.user_id, q.query)

@app.post("/api/run")
def run_legacy(q: Query):
    """Legacy endpoint; now routes through the compiled LangGraph graph."""
    return _invoke_graph(q.user_id, q.query)

# Simple health and route inspection
@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.get("/__routes")
def routes() -> List[str]:
    return [r.path for r in app.routes]

# Helper endpoints for demo: add a medication to private memory (upsert)
class MedInput(BaseModel):
    user_id: str = "demo-user"
    name: str
    value: str = ""

@app.post("/api/memory/add_med")
def add_med(m: MedInput):
    base = re.sub(r"\b(\d+\s?mg|\d+\s?mcg|\d+\s?ml)\b", "", m.name, flags=re.IGNORECASE).strip().lower()
    doc_id = f"{m.user_id}:med:{base}"
    doc = {
        "user_id": m.user_id,
        "entity": "medication",
        "name": m.name.strip(),
        "normalized": {"ingredient": base},
        "value": m.value,
        "confidence": 0.95,
        "embedding": embed([m.name])[0]
    }
    es.index(index=settings.es_private_index, id=doc_id, document=doc)
    return {"ok": True}
