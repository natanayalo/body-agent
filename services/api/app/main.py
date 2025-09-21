from fastapi import FastAPI, Query as QueryParam
from fastapi.responses import HTMLResponse, StreamingResponse
from starlette.routing import Route
from pydantic import BaseModel, Field
from typing import List, AsyncGenerator, Any, Dict, cast, Literal
import logging
import os
import re
import json
from datetime import datetime, timezone

from app.config import settings
from app.config.logging import configure_logging

from app.tools.es_client import ensure_indices, get_es_client
from app.graph.state import BodyState
from app.tools.language import normalize_language_code
from app.graph.build import build_graph
from app.graph.nodes import risk_ml
from contextlib import asynccontextmanager

from app.tools.embeddings import embed
from app.tools.crypto import encrypt_for_user
from scalar_fastapi import Layout, Theme, get_scalar_api_reference

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
    app.state.last_trace = []
    app.state.last_risk = {}
    app.state.last_run_completed_at = None
    yield


app = FastAPI(title="Body Agent API", lifespan=lifespan, docs_url=None, redoc_url=None)


@app.get("/docs", include_in_schema=False)
def scalar_docs() -> HTMLResponse:
    return get_scalar_api_reference(
        openapi_url=app.openapi_url,
        title="Body Agent API Docs",
        layout=Layout.MODERN,
        theme=Theme.DEEP_SPACE,
        hide_models=True,
        hide_client_button=True,
        hide_download_button=True,
    )


class Query(BaseModel):
    user_id: str = Field(..., min_length=1)
    query: str = Field(..., min_length=1)
    lang: str | None = Field(default=None, min_length=2, max_length=5)


def _initial_state(q: Query, lang_override: str | None) -> BodyState:
    state: BodyState = {"user_id": q.user_id, "user_query": q.query, "messages": []}
    normalized = normalize_language_code(lang_override or q.lang)
    if normalized:
        state["language"] = cast(Literal["en", "he"], normalized)
    return state


def _record_run_metadata(final_state: BodyState) -> None:
    debug = final_state.get("debug") or {}
    trace = debug.get("trace") or []
    app.state.last_trace = list(trace)
    app.state.last_risk = debug.get("risk", {})
    app.state.last_run_completed_at = datetime.now(timezone.utc).isoformat()


@app.post("/api/graph/run")
async def run_graph(q: Query, lang: str | None = QueryParam(default=None)):
    logger.info(f"Running graph for user {q.user_id}")
    try:
        state = _initial_state(q, lang)
        final_state = await app.state.graph.ainvoke(state)
        logger.debug(f"Query: {final_state.get('user_query_redacted', q.query)}")
        logger.info(f"Graph run completed for user {q.user_id}")
        _record_run_metadata(final_state)
        return {"state": final_state}
    except Exception as e:
        logger.error(f"Graph run failed for user {q.user_id}: {str(e)}", exc_info=True)
        raise


@app.post("/api/graph/stream")
async def stream_graph(
    q: Query, lang: str | None = QueryParam(default=None)
) -> StreamingResponse:
    logger.info(f"Streaming graph for user {q.user_id}")
    state = _initial_state(q, lang)

    async def _stream_chunks() -> AsyncGenerator[str, None]:
        try:
            # Keep an accumulated view of the state while streaming deltas
            current_state: Dict[str, Any] = dict(state)

            async for chunk in app.state.graph.astream(state):
                node, delta = next(iter(chunk.items()))
                if delta:
                    # Update our accumulated state (extend lists, assign scalars)
                    try:
                        if isinstance(delta, dict):
                            for k, v in delta.items():
                                if isinstance(v, list) and isinstance(
                                    current_state.get(k), list
                                ):
                                    current_state[k].extend(v)  # type: ignore[index]
                                else:
                                    current_state[k] = v
                    except Exception as e:
                        logger.warning(
                            f"Error updating stream state with delta {delta}: {e}"
                        )
                    yield f"data: {json.dumps({'node': node, 'delta': delta})}\n\n"

            # Emit the exact final state. Prefer a fresh ainvoke; fallback to accumulated
            try:
                final_state: BodyState = await app.state.graph.ainvoke(state)
            except Exception:
                final_state = cast(BodyState, current_state)

            yield f"data: {json.dumps({'final': {'state': final_state}})}\n\n"
            logger.info(f"Graph stream completed for user {q.user_id}")
            _record_run_metadata(final_state)
        except Exception as e:
            logger.error(
                f"Graph stream failed for user {q.user_id}: {str(e)}", exc_info=True
            )
            # Yield a final error message to the client if possible
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(_stream_chunks(), media_type="text/event-stream")


@app.post("/api/run")
async def run_legacy(q: Query, lang: str | None = QueryParam(default=None)):
    """Legacy endpoint; now routes through the compiled LangGraph graph."""
    logger.info(f"Legacy endpoint called for user {q.user_id}")
    return await run_graph(q, lang)


# Simple health and route inspection
@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/api/debug/risk")
def debug_risk():
    thresholds = risk_ml._parse_thresholds(
        os.getenv("RISK_THRESHOLDS", "urgent_care:0.55,see_doctor:0.50")
    )
    labels = [
        s.strip()
        for s in os.getenv(
            "RISK_LABELS", "urgent_care,see_doctor,self_care,info_only"
        ).split(",")
        if s.strip()
    ]
    return {
        "last": getattr(app.state, "last_risk", {}),
        "thresholds": thresholds,
        "labels": labels,
    }


@app.get("/api/debug/trace")
def debug_trace():
    return {
        "completed_at": getattr(app.state, "last_run_completed_at", None),
        "trace": getattr(app.state, "last_trace", []),
    }


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
        # Store sensitive value encrypted at rest
        "value": encrypt_for_user(m.user_id, m.value),
        "value_encrypted": True,
        "confidence": 0.95,
        "embedding": embed([m.name])[0],
    }
    get_es_client().index(index=settings.es_private_index, id=doc_id, document=doc)
    return {"ok": True}


@app.get("/__routes")
def routes() -> List[str]:
    return [r.path for r in app.routes if isinstance(r, Route)]
