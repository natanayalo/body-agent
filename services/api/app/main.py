from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
import logging
import re

from app.config import settings
from app.config.logging import configure_logging
from app.tools.es_client import ensure_indices
from app.graph.state import BodyState
from app.graph.build import build_graph
from app.tools.es_client import es
from app.tools.embeddings import embed

# Configure logging at startup
configure_logging()
logger = logging.getLogger(__name__)

# keep node imports available (legacy)

app = FastAPI(title="Body Agent API")


class Query(BaseModel):
    user_id: str = "demo-user"
    query: str


@app.on_event("startup")
async def startup():
    ensure_indices()
    app.state.graph = build_graph().compile()


def _invoke_graph(user_id: str, text: str) -> BodyState:
    state: BodyState = {"user_id": user_id, "user_query": text, "messages": []}
    return app.state.graph.invoke(state)


@app.post("/api/graph/run")
def run_graph(q: Query):
    logger.info(f"Running graph for user {q.user_id}")
    logger.debug(f"Query: {q.query}")
    try:
        result = _invoke_graph(q.user_id, q.query)
        logger.info(f"Graph run completed for user {q.user_id}")
        return result
    except Exception as e:
        logger.error(f"Graph run failed for user {q.user_id}: {str(e)}", exc_info=True)
        raise


@app.post("/api/run")
def run_legacy(q: Query):
    """Legacy endpoint; now routes through the compiled LangGraph graph."""
    logger.info(f"Legacy endpoint called for user {q.user_id}")
    return run_graph(q)


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
