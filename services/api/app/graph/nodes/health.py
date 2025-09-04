from typing import Any
from app.graph.state import BodyState
from app.tools.es_client import es
from app.tools.embeddings import embed
from app.config import settings


# Very conservative RAG: retrieve relevant public KB snippets


def run(state: BodyState) -> BodyState:
    q = state["user_query"]
    if mem := state.get("memory_facts"):
        # Add key memory terms to query (e.g., medication names)
        terms = [m.get("name") for m in mem if m.get("entity") in {"medication","allergy"}]
        if terms:
            q += "\nContext:" + ", ".join(t for t in terms if t)
    vector = embed([q])[0]
    body = {
        "knn": {"field": "embedding", "query_vector": vector, "k": 8, "num_candidates": 64},
        "_source": {"excludes": ["embedding"]},
        "size": 8
    }
    res = es.search(index=settings.es_public_index, body=body)
    docs = [h["_source"] for h in res["hits"]["hits"]]


    # Simple heuristic advice (no LLM): pick top snippet titles & sections
    citations = []
    alerts = []
    messages = []
    for d in docs[:3]:
        if d.get("section", "").lower() in {"warnings","interactions"}:
            alerts.append(f"Check: {d.get('title')} — {d.get('section')}")
            citations.append(d.get("source_url", ""))
    if not messages:
        messages.append({"role":"assistant","content":"I found guidance and possible warnings. Review the summary and citations."})


    state["public_snippets"] = docs
    state["alerts"] = alerts
    state["citations"] = [c for c in citations if c]
    state.setdefault("messages", []).extend(messages)
    return state
