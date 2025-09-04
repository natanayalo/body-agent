from fastapi import FastAPI
from pydantic import BaseModel
from app.config import settings
from app.tools.es_client import ensure_indices
from app.graph.state import BodyState
from app.graph.build import build_graph

# Wire up nodes (legacy linear path kept for back-compat)
from app.graph.nodes import supervisor, memory, health, places, planner, critic

app = FastAPI(title="Body Agent API")

class Query(BaseModel):
    user_id: str = "demo-user"
    query: str

@app.on_event("startup")
async def startup():
    ensure_indices()
    # Compile the LangGraph once
    app.state.graph = build_graph().compile()

def _invoke_graph(user_id: str, text: str) -> BodyState:
    state: BodyState = {
        "user_id": user_id,
        "user_query": text,
        "messages": []
    }
    # Execute compiled graph
    return app.state.graph.invoke(state)

@app.post("/api/graph/run")
def run_graph(q: Query):
    return _invoke_graph(q.user_id, q.query)

@app.post("/api/run")
def run(q: Query):
    """Legacy endpoint; now routes through the compiled LangGraph graph."""
    return _invoke_graph(q.user_id, q.query)


# Helper endpoints for demo: add a medication to private memory
class MedInput(BaseModel):
    user_id: str = "demo-user"
    name: str
    value: str = ""


from app.tools.es_client import es
from app.tools.embeddings import embed


@app.post("/api/memory/add_med")
def add_med(m: MedInput):
    doc = {
        "user_id": m.user_id,
        "entity": "medication",
        "name": m.name,
        "value": m.value,
        "confidence": 0.95,
        "embedding": embed([m.name])[0]
    }
    es.index(index=settings.es_private_index, document=doc)
    return {"ok": True}
