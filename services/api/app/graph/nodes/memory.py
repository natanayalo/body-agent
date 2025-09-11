from app.graph.state import BodyState
from app.tools.embeddings import embed
from app.config import settings
import re


def _base_name(name: str) -> str:
    return (
        re.sub(r"\b(\d+\s?(mg|mcg|ml))\b", "", name, flags=re.IGNORECASE)
        .strip()
        .lower()
    )


def run(state: BodyState, es_client) -> BodyState:
    es = es_client
    vector = embed([state.get("user_query", "")])[0]
    body = {
        "knn": {
            "field": "embedding",
            "query_vector": vector,
            "k": 8,
            "num_candidates": 50,
        },
        "_source": {"excludes": ["embedding"]},
    }
    if user_id := state.get("user_id"):
        body["knn"]["filter"] = {"term": {"user_id": user_id}}

    res = es.search(index=settings.es_private_index, body=body)
    hits = [h["_source"] for h in res["hits"]["hits"]]

    seen = set()
    uniq = []
    for m in hits:
        ent = m.get("entity")
        base = (m.get("normalized") or {}).get("ingredient") or _base_name(
            m.get("name", "")
        )
        key = (ent, base)
        if key not in seen:
            seen.add(key)
            uniq.append(m)
    state["memory_facts"] = uniq
    return state
