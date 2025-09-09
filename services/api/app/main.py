from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import List
import logging
import re

from app.config import settings
from app.tools.es_client import ensure_indices
from app.graph.state import BodyState
from app.graph.build import build_graph
from app.tools.es_client import es
from app.tools.embeddings import embed

logger = logging.getLogger(__name__)


async def run_and_await_completion(graph, state: BodyState):
    """Execute the graph and wait for completion"""
    # Run the compiled graph
    results = await graph.abatch([state])
    return results[0]


app = FastAPI(title="Body Agent API")


async def _invoke_graph(user_id: str, text: str) -> BodyState:
    state: BodyState = {"user_id": user_id, "user_query": text, "messages": []}
    result = await run_and_await_completion(app.state.graph, state)
    return result


class Query(BaseModel):
    user_id: str = Field(..., min_length=1)
    query: str = Field(..., min_length=1)


@app.on_event("startup")
async def startup():
    ensure_indices()
    app.state.graph = build_graph().compile()


@app.post("/api/graph/run")
async def run_graph(q: Query):
    logger.info(f"Running graph for user {q.user_id}")
    logger.debug(f"Query: {q.query}")
    try:
        state = await _invoke_graph(q.user_id, q.query)
        logger.info(f"Graph run completed for user {q.user_id}")
        return {"state": state}
    except Exception as e:
        logger.error(f"Graph run failed for user {q.user_id}: {str(e)}", exc_info=True)
        raise


@app.post("/api/run")
async def run_legacy(q: Query):
    """Legacy endpoint; now routes through the compiled LangGraph graph."""
    logger.info(f"Legacy endpoint called for user {q.user_id}")
    return await run_graph(q)


# Simple health and route inspection
@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/__routes")
def routes() -> List[str]:
    return [r.path for r in app.routes]


# Helper endpoints for demo: add a medication to private memory (upsert)
class MedInput(BaseModel):
    user_id: str = Field(..., min_length=1)
    name: str
    value: str = ""


@app.post("/api/memory/add_med")
def add_med(m: MedInput):
    base = (
        re.sub(r"\b(\d+\s?mg|\d+\s?mcg|\d+\s?ml)\b", "", m.name, flags=re.IGNORECASE)
        .strip()
        .lower()
    )
    doc_id = f"{m.user_id}:med:{base}"
    doc = {
        "user_id": m.user_id,
        "entity": "medication",
        "name": m.name.strip(),
        "normalized": {"ingredient": base},
        "value": m.value,
        "confidence": 0.95,
        "embedding": embed([m.name])[0],
    }
    es.index(index=settings.es_private_index, id=doc_id, document=doc)
    return {"ok": True}
