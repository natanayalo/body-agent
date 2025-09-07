from app.graph.state import BodyState
from app.tools.es_client import es
from app.tools.embeddings import embed
from app.config import settings
import re


def run(state: BodyState) -> BodyState:
    q = state["user_query"]

    # Build a set of normalized ingredients from memory (e.g., {"ibuprofen", "warfarin"})
    mem_ings = set()
    for m in state.get("memory_facts") or []:
        ing = (m.get("normalized") or {}).get("ingredient") or (
            m.get("name") or ""
        ).lower()
        if ing:
            mem_ings.add(ing)

    # Add memory terms to the query for retrieval context
    if mem_ings:
        q += "\nContext:" + ", ".join(sorted(mem_ings))

    # k-NN first
    vector = embed([q])[0]
    body_knn = {
        "knn": {
            "field": "embedding",
            "query_vector": vector,
            "k": 8,
            "num_candidates": 64,
        },
        "_source": {"excludes": ["embedding"]},
        "size": 8,
    }
    res = es.search(index=settings.es_public_index, body=body_knn)
    hits = res["hits"]["hits"]

    # Fallback to BM25 if no k-NN hits (tiny corpora safety net)
    if not hits:
        body_bm25 = {
            "query": {"multi_match": {"query": q, "fields": ["title^2", "text"]}},
            "_source": {"excludes": ["embedding"]},
            "size": 8,
        }
        res = es.search(index=settings.es_public_index, body=body_bm25)
        hits = res["hits"]["hits"]

    docs = [h["_source"] for h in hits]

    citations: list[str] = []
    alerts: list[str] = []
    messages: list[dict] = []

    # Build a memory ingredient set for generic interaction gating
    mem_ings = set()
    for m in state.get("memory_facts") or []:
        if m.get("entity") == "medication":
            ing = (m.get("normalized") or {}).get("ingredient") or (
                m.get("name") or ""
            ).lower()
            if ing:
                mem_ings.add(ing)

    def _norm(s: str) -> str:
        return re.sub(r"\W+", " ", (s or "")).lower()

    for d in docs[:3]:
        section = (d.get("section", "") or "").lower()
        title = _norm(d.get("title"))
        text = _norm(d.get("text"))
        add_alert = False
        if section == "warnings":
            add_alert = True
        elif section == "interactions":
            # Only alert if >=2 distinct memory meds appear in the snippet
            seen = 0
            for ing in mem_ings:
                if ing and (ing in title or ing in text):
                    seen += 1
                if seen >= 2:
                    add_alert = True
                    break
        if add_alert:
            alerts.append(f"Check: {d.get('title')} — {d.get('section')}")
        citations.append(d.get("source_url", ""))

    if not messages:
        messages.append(
            {
                "role": "assistant",
                "content": "I found guidance and possible warnings. Review the summary and citations.",
            }
        )

    state["public_snippets"] = docs
    state["alerts"] = alerts
    # dedupe citations
    seen_citations = set()
    dedup = []
    for c in citations:
        if c and c not in seen_citations:
            seen_citations.add(c)
            dedup.append(c)
    state["citations"] = dedup
    state.setdefault("messages", []).extend(messages)
    return state
