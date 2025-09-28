import re
import logging
from typing import Iterable

from app.graph.state import BodyState
from app.tools.es_client import get_es_client
from app.tools.embeddings import embed
from app.config import settings
from app.tools.language import DEFAULT_LANGUAGE, normalize_language_code
from app.tools import symptom_registry
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


def _doc_identity(doc: dict) -> str:
    if not isinstance(doc, dict):
        return ""
    lang_raw = doc.get("language")
    lang = normalize_language_code(lang_raw) if lang_raw else ""
    if src := doc.get("source_url"):
        return f"src::{src}::{lang}"
    title = doc.get("title")
    section = doc.get("section")
    return f"title::{title}::{section}::{lang}"


def _merge_docs(*groups: Iterable[dict]) -> list[dict]:
    merged: list[dict] = []
    seen: set[str] = set()
    for group in groups:
        for doc in group or []:
            key = _doc_identity(doc)
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            merged.append(doc)
    return merged


def _fetch_registry_docs(es, refs: list[dict]) -> list[dict]:
    docs: list[dict] = []
    if not refs:
        return docs

    searches: list[dict] = []
    for ref in refs:
        if not isinstance(ref, dict):
            continue

        must: list[dict] = []
        for field in ("source_url", "title", "section", "language"):
            value = ref.get(field)
            if not value:
                continue
            must.append({"match_phrase": {field: value}})

        if not must:
            continue

        searches.append({"index": settings.es_public_index})
        searches.append(
            {
                "query": {"bool": {"must": must}},
                "_source": {"excludes": ["embedding"]},
                "size": 1,
            }
        )

    if not searches:
        return docs

    try:
        responses = es.msearch(body=searches).get("responses", [])
    except (TransportError, RequestError) as exc:
        logger.warning("Registry doc msearch failed: %s", exc)
        return docs
    except Exception as exc:  # pragma: no cover
        logger.error("Unexpected registry msearch error: %s", exc, exc_info=True)
        return docs

    for res in responses or []:
        if not isinstance(res, dict):
            continue
        if res.get("error"):
            logger.warning("Registry doc msearch returned error: %s", res.get("error"))
            continue
        hit = (res.get("hits", {}).get("hits") or [None])[0]
        if hit and isinstance(hit, dict):
            doc = hit.get("_source")
            if isinstance(doc, dict):
                docs.append(doc)

    return docs


def run(state: BodyState, es_client=None) -> BodyState:
    if "user_query" not in state and "user_query_redacted" not in state:
        raise KeyError("user_query")

    raw_query = state.get("user_query_redacted") or state.get("user_query", "")
    pivot_query = (state.get("user_query_pivot") or "").strip()
    parts = [p for p in (pivot_query, raw_query) if p]
    deduped_parts = list(dict.fromkeys(parts))
    search_query = deduped_parts[0] if deduped_parts else raw_query
    combined_query = " ".join(deduped_parts).strip() or search_query
    mem = state.get("memory_facts") or []
    med_terms = _norm_med_terms(mem)
    es = es_client if es_client else get_es_client()
    preferred_lang = _preferred_language(state)
    registry_matches = symptom_registry.match_query(raw_query)
    expansion_terms = symptom_registry.expansion_terms(registry_matches, preferred_lang)
    registry_docs = _fetch_registry_docs(
        es, symptom_registry.doc_refs(registry_matches)
    )

    docs = []

    # Try kNN firs
    try:
        vector_query = combined_query
        if expansion_terms:
            vector_query = " ".join([combined_query] + expansion_terms)
        vector = embed([vector_query])[0]
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
    except (TransportError, RequestError) as e:  # pragma: no cover
        logger.warning(f"kNN search failed: {e}. Falling back to BM25.")
        docs = []
    except Exception as e:  # pragma: no cover
        logger.error(
            f"An unexpected error occurred during kNN search: {e}", exc_info=True
        )
        docs = []

    # BM25 fallback — IMPORTANT: include per-med 'title' matches in lowercase
    if not docs:
        try:
            should = [
                {"match": {"text": {"query": search_query, "boost": 2.0}}},
                {"match": {"title": {"query": search_query, "boost": 1.8}}},
            ]

            if pivot_query and raw_query and pivot_query != raw_query:
                should.append({"match": {"text": {"query": raw_query, "boost": 1.2}}})
                should.append({"match": {"title": {"query": raw_query, "boost": 1.1}}})

            for term in expansion_terms:
                should.append({"match": {"title": {"query": term, "boost": 1.6}}})
                should.append({"match": {"text": {"query": term, "boost": 1.4}}})

            for t in med_terms:
                should.append({"match": {"title": {"query": t, "boost": 1.2}}})
                should.append({"match": {"text": {"query": t, "boost": 1.1}}})

            for section, boost in (("general", 1.5), ("warnings", 1.3)):
                should.append(
                    {"match": {"section": {"query": section, "boost": boost}}}
                )

            bm25_body = {
                "query": {"bool": {"should": should, "minimum_should_match": 1}},
                "_source": {"excludes": ["embedding"]},
                "size": 8,
            }
            res = es.search(index=settings.es_public_index, body=bm25_body)
            docs.extend([h["_source"] for h in res.get("hits", {}).get("hits", [])])
        except (TransportError, RequestError) as e:  # pragma: no cover
            logger.warning(f"BM25 search failed: {e}.")
        except Exception as e:  # pragma: no cover
            logger.error(
                f"An unexpected error occurred during BM25 search: {e}", exc_info=True
            )

    docs = _merge_docs(registry_docs, docs)
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
