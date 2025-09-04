from typing import Any
from app.graph.state import BodyState
from app.tools.es_client import es
from app.tools.embeddings import embed
from app.config import settings


# Query private_user_memory for facts relevant to the query

def run(state: BodyState) -> BodyState:
    vector = embed([state["user_query"]])[0]
    body = {
    "knn": {
        "field": "embedding",
        "query_vector": vector,
        "k": 8,
        "num_candidates": 50,
        },
        "_source": {"excludes": ["embedding"]}
    }
    res = es.search(index=settings.es_private_index, body=body)
    state["memory_facts"] = [h["_source"] for h in res["hits"]["hits"]]
    return state
