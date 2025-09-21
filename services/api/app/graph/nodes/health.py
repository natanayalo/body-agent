import re
import logging
from app.graph.state import BodyState
from app.tools.es_client import get_es_client
from app.tools.embeddings import embed
from app.config import settings
from app.tools.language import DEFAULT_LANGUAGE, normalize_language_code
from elasticsearch import TransportError, RequestError

logger = logging.getLogger(__name__)


def _norm_med_terms(mem_facts: list[dict]) -> list[str]:
    terms = []
    for m in mem_facts or []:
        if m.get("entity") == "medication":
            ingr = (m.get("normalized") or {}).get("ingredient")
            if ingr:
                terms.append(ingr.lower())
            else:
                name = (m.get("name") or "").lower()
                # crude token pick: take first word
                tok = re.split(r"\W+", name.strip())[0]
                if tok:
                    terms.append(tok)
    # de-dupe, keep order
    seen, out = set(), []
    for t in terms:
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _preferred_language(state: BodyState) -> str:
    lang = state.get("language")
    normalized = normalize_language_code(lang) if lang else None
    return normalized or DEFAULT_LANGUAGE


def _prioritize_language(docs: list[dict], preferred: str) -> list[dict]:
    if not docs:
        return docs

    primary, secondary = [], []
    for doc in docs:
        doc_lang_raw = doc.get("language")
        doc_lang = normalize_language_code(doc_lang_raw) if doc_lang_raw else None
        if doc_lang == preferred:
            primary.append(doc)
        else:
            secondary.append(doc)
    return primary + secondary


def run(state: BodyState, es_client=None) -> BodyState:
    q = state.get("user_query_redacted", state["user_query"])
    mem = state.get("memory_facts") or []
    med_terms = _norm_med_terms(mem)
    es = es_client if es_client else get_es_client()
    docs = []
    preferred_lang = _preferred_language(state)

    # Try kNN firs
    try:
        vector = embed([q])[0]
        knn_body = {
            "knn": {
                "field": "embedding",
                "query_vector": vector,
                "k": 8,
                "num_candidates": 64,
            },
            "_source": {"excludes": ["embedding"]},
            "size": 8,
        }
        res = es.search(index=settings.es_public_index, body=knn_body)
        docs = [h["_source"] for h in res.get("hits", {}).get("hits", [])]
    except (TransportError, RequestError) as e:
        logger.warning(f"kNN search failed: {e}. Falling back to BM25.")
        docs = []
    except Exception as e:
        logger.error(
            f"An unexpected error occurred during kNN search: {e}", exc_info=True
        )
        docs = []

    # BM25 fallback — IMPORTANT: include per-med 'title' matches in lowercase
    if not docs:
        try:
            should = [
                {"match": {"text": q}},
                {"match": {"title": q}},
            ]
            for t in med_terms:
                should.append({"match": {"title": t}})
                should.append({"match": {"text": t}})
            bm25_body = {
                "query": {"bool": {"should": should, "minimum_should_match": 1}},
                "_source": {"excludes": ["embedding"]},
                "size": 8,
            }
            res = es.search(index=settings.es_public_index, body=bm25_body)
            docs.extend([h["_source"] for h in res.get("hits", {}).get("hits", [])])
        except (TransportError, RequestError) as e:
            logger.warning(f"BM25 search failed: {e}.")
        except Exception as e:
            logger.error(
                f"An unexpected error occurred during BM25 search: {e}", exc_info=True
            )

    docs = _prioritize_language(docs, preferred_lang)

    # Build alerts & citations
    alerts = state.get("alerts", [])
    citations = state.get("citations", [])
    messages = state.get("messages", [])

    alerts_before = len(alerts)
    citations_before = len(citations)

    for d in docs[:3]:
        sec = str(d.get("section", "")).lower()
        alert_msg = f"Check: {d.get('title')} — {d.get('section')}"
        if sec == "warnings" and alert_msg not in alerts:
            alerts.append(alert_msg)
        elif sec == "interactions" and alert_msg not in alerts:
            # Check if at least two of the user's known medications are mentioned
            doc_content = (d.get("title", "") + " " + d.get("text", "")).lower()
            mentioned_meds = sum(1 for med in med_terms if med in doc_content)
            if mentioned_meds >= 2:
                alerts.append(alert_msg)

        if (src := d.get("source_url")) and src not in citations:
            citations.append(src)

    new_info_found = len(alerts) > alerts_before or len(citations) > citations_before
    if new_info_found or not state.get("messages"):  # if new info or no messages yet
        if not any("I found guidance" in m["content"] for m in messages):
            messages.append(
                {
                    "role": "assistant",
                    "content": "I found guidance and possible warnings. Review the summary and citations.",
                }
            )

    state["public_snippets"] = docs
    state["alerts"] = alerts
    state["citations"] = citations
    state["messages"] = messages
    return state
