from fastapi import FastAPI
from pydantic import BaseModel
from app.config import settings
from app.tools.es_client import ensure_indices
from app.graph.state import BodyState


# Wire up nodes as a simple pipeline (LangGraph-like, but linear for MVP)
from app.graph.nodes import supervisor, memory, health, places, planner, critic


app = FastAPI(title="Body Agent API")


class Query(BaseModel):
    user_id: str = "demo-user"
    query: str


@app.on_event("startup")
async def startup():
    ensure_indices()


@app.post("/api/run")
def run(q: Query):
    state: BodyState = {
    "user_id": q.user_id,
    "user_query": q.query,
    "messages": []
    }
    # Supervisor decides high-level path
    state = supervisor.run(state)


    # Memory lookup first
    state = memory.run(state)


    # Branch by intent
    if state["intent"] in ("meds", "symptom"):
        state = health.run(state)
    if state["intent"] == "appointment":
        state = places.run(state)


    # Planner + critic
    state = planner.run(state)
    state = critic.run(state)


    return state


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
