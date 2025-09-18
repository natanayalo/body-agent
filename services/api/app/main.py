from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from starlette.routing import Route
from pydantic import BaseModel, Field
from typing import List, AsyncGenerator, Any, Dict, cast
import logging
import os
import re
import json

from app.config import settings
from app.config.logging import configure_logging

from app.tools.es_client import ensure_indices, get_es_client
from app.graph.state import BodyState
from app.graph.build import build_graph
from contextlib import asynccontextmanager

from app.tools.embeddings import embed

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    # Avoid bootstrapping indices when running under pytest or explicit test env
    if os.getenv("PYTEST_CURRENT_TEST") or os.getenv("APP_ENV") == "test":
        logger.info("Skipping index bootstrap in test mode")
    else:
        ensure_indices()
    app.state.graph = build_graph()
    yield


app = FastAPI(title="Body Agent API", lifespan=lifespan)


class Query(BaseModel):
    user_id: str = Field(..., min_length=1)
    query: str = Field(..., min_length=1)


@app.post("/api/graph/run")
async def run_graph(q: Query):
    logger.info(f"Running graph for user {q.user_id}")
    try:
        state: BodyState = {"user_id": q.user_id, "user_query": q.query, "messages": []}
        final_state = await app.state.graph.ainvoke(state)
        logger.debug(f"Query: {final_state.get('user_query_redacted', q.query)}")
        logger.info(f"Graph run completed for user {q.user_id}")
        return {"state": final_state}
    except Exception as e:
        logger.error(f"Graph run failed for user {q.user_id}: {str(e)}", exc_info=True)
        raise


@app.post("/api/graph/stream")
async def stream_graph(q: Query) -> StreamingResponse:
    logger.info(f"Streaming graph for user {q.user_id}")
    state: BodyState = {"user_id": q.user_id, "user_query": q.query, "messages": []}

    async def _stream_chunks() -> AsyncGenerator[str, None]:
        try:
            # Keep an accumulated view of the state while streaming deltas
            current_state: Dict[str, Any] = dict(state)

            async for chunk in app.state.graph.astream(state):
                node, delta = next(iter(chunk.items()))
                if delta:
                    # Update our accumulated state
                    try:
                        if isinstance(delta, dict):
                            current_state.update(delta)
                    except Exception:
                        pass
                    yield f"data: {json.dumps({'node': node, 'delta': delta})}\n\n"

            # Emit the exact final state. Prefer a fresh ainvoke; fallback to accumulated
            try:
                final_state: BodyState = await app.state.graph.ainvoke(state)
            except Exception:
                final_state = cast(BodyState, current_state)

            yield f"data: {json.dumps({'final': {'state': final_state}})}\n\n"
            logger.info(f"Graph stream completed for user {q.user_id}")
        except Exception as e:
            logger.error(
                f"Graph stream failed for user {q.user_id}: {str(e)}", exc_info=True
            )
            # Yield a final error message to the client if possible
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(_stream_chunks(), media_type="text/event-stream")


@app.post("/api/run")
async def run_legacy(q: Query):
    """Legacy endpoint; now routes through the compiled LangGraph graph."""
    logger.info(f"Legacy endpoint called for user {q.user_id}")
    return await run_graph(q)


# Simple health and route inspection
@app.get("/healthz")
def healthz():
    return {"ok": True}


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
    get_es_client().index(index=settings.es_private_index, id=doc_id, document=doc)
    return {"ok": True}


@app.get("/__routes")
def routes() -> List[str]:
    return [r.path for r in app.routes if isinstance(r, Route)]
