from typing import Any, Dict

from app.graph.state import BodyState
from app.tools.es_client import get_es_client
from app.tools.embeddings import embed
from app.config import settings


def extract_preferences(facts: list[Dict[str, Any]]) -> Dict[str, Any]:
    prefs: Dict[str, Any] = {}
    if not facts:
        return prefs

    preferred_kinds: list[str] = []
    for doc in facts:
        if doc.get("entity") != "preference":
            continue
        name = (doc.get("name") or "").strip().lower()
        value = (doc.get("value") or "").strip()
        if not name or not value:
            continue

        if name in {"preferred_kind", "preferred_kinds"}:
            values = [v.strip().lower() for v in value.split(",") if v.strip()]
            for v in values:
                if v and v not in preferred_kinds:
                    preferred_kinds.append(v)
        elif name in {"preferred_hours", "hours_window"}:
            prefs["hours_window"] = value.lower()
        elif name == "max_distance_km":
            try:
                prefs["max_distance_km"] = float(value)
            except (TypeError, ValueError):
                continue
        elif name == "insurance_plan":
            prefs["insurance_plan"] = value

    if preferred_kinds:
        prefs["preferred_kinds"] = preferred_kinds
    return prefs


def run(state: BodyState, es_client=None) -> BodyState:
    user_id = state.get("user_id")
    hits = []
    es = es_client if es_client else get_es_client()

    # Prefer exact user_id term search.
    if user_id:
        body = {
            "query": {"term": {"user_id": user_id}},
            "_source": {"excludes": ["embedding"]},
            "size": 16,
        }
        res = es.search(index=settings.es_private_index, body=body)
        hits = res.get("hits", {}).get("hits", [])

    # Optional: if nothing found, fallback to semantic (dev convenience)
    if not hits and user_id:
        q = state.get("user_query_redacted", state["user_query"])
        vector = embed([q])[0]
        body = {
            "knn": {
                "field": "embedding",
                "query_vector": vector,
                "k": 8,
                "num_candidates": 50,
                "filter": {"term": {"user_id": user_id}},
            },
            "_source": {"excludes": ["embedding"]},
        }
        res = es.search(index=settings.es_private_index, body=body)
        hits = res.get("hits", {}).get("hits", [])
    facts = [h["_source"] for h in hits]
    state["memory_facts"] = facts
    prefs = extract_preferences(facts)
    if prefs:
        state["preferences"] = prefs
    return state
