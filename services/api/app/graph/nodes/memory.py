from app.graph.state import BodyState
from app.tools.embeddings import embed
from app.config import settings
import re
from typing import Any


def _base_name(name: str) -> str:
    return (
        re.sub(r"\b(\d+\s?(mg|mcg|ml))\b", "", name, flags=re.IGNORECASE)
        .strip()
        .lower()
    )


def run(state: BodyState, es_client: Any) -> BodyState:
    es = es_client
    user_id = state.get("user_id")

    if not user_id:
        state["memory_facts"] = []
        return state

    body: dict[str, Any]

    if settings.embeddings_model == "__stub__":
        # In stub mode (CI/testing), k-NN is unreliable.
        # Retrieve all documents for the user to ensure test stability.
        body = {
            "query": {"term": {"user_id": user_id}},
            "size": 100,  # Assuming a user won't have more than 100 facts in a test
            "_source": {"excludes": ["embedding"]},
        }
    else:
        # In production, use k-NN to find relevant facts.
        vector = embed([state.get("user_query_redacted", "")])[0]
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
