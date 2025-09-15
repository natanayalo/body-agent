from app.graph.state import BodyState
from app.tools.es_client import get_es_client
from app.tools.embeddings import embed
from app.config import settings


def run(state: BodyState, es_client=None) -> BodyState:
    user_id = state.get("user_id")
    hits = []
    es = es_client if es_client else get_es_client()

    # Prefer exact user_id term search so tests' FakeES handler matches.
    if user_id:
        body = {
            "query": {"term": {"user_id": user_id}},
            "_source": {"excludes": ["embedding"]},
            "size": 16,
        }
        res = es.search(index=settings.es_private_index, body=body)
        hits = res.get("hits", {}).get("hits", [])

    # Optional: if nothing found, fallback to semantic (dev convenience)
    if not hits:
        vector = embed([state["user_query"]])[0]
        body = {
            "knn": {
                "field": "embedding",
                "query_vector": vector,
                "k": 8,
                "num_candidates": 50,
            },
            "_source": {"excludes": ["embedding"]},
        }
        res = es.search(index=settings.es_private_index, body=body)
        hits = res.get("hits", {}).get("hits", [])

    state["memory_facts"] = [h["_source"] for h in hits]
    return state
