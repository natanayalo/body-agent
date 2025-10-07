from typing import Any, Dict

from app.graph.state import BodyState
from app.tools.es_client import get_es_client
from app.tools.embeddings import embed
from app.tools.med_normalize import normalize_fact
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
        value_raw = doc.get("value")
        if not name or value_raw is None:
            continue

        if isinstance(value_raw, str):
            value = value_raw.strip()
            if not value:
                continue
        else:
            value = value_raw

        if name in {"preferred_kind", "preferred_kinds"}:
            if isinstance(value, str):
                values = [v.strip().lower() for v in value.split(",") if v.strip()]
            elif isinstance(value, (list, tuple, set)):
                values = [str(v).strip().lower() for v in value if str(v).strip()]
            else:
                values = [str(value).strip().lower()]
            for v in values:
                if v and v not in preferred_kinds:
                    preferred_kinds.append(v)
        elif name in {"preferred_hours", "hours_window"}:
            if isinstance(value, str):
                prefs["hours_window"] = value.lower()
            elif isinstance(value, (list, tuple, set)) and len(value) > 0:
                prefs["hours_window"] = str(next(iter(value))).strip().lower()
            else:
                prefs["hours_window"] = str(value).strip().lower()
        elif name in {"max_travel_km", "max_distance_km"}:
            try:
                numeric = (
                    float(value)
                    if isinstance(value, (int, float))
                    else float(str(value).strip())
                )
            except (TypeError, ValueError):
                continue
            prefs["max_travel_km"] = numeric
        elif name == "insurance_plan":
            prefs["insurance_plan"] = str(value).strip()

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
    facts = []
    for hit in hits:
        doc = hit.get("_source", {})
        if isinstance(doc, dict):
            normalize_fact(doc)
            facts.append(doc)
    state["memory_facts"] = facts
    prefs = extract_preferences(facts)
    if prefs:
        state["preferences"] = prefs
    return state
