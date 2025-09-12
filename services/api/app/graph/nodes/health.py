from app.graph.state import BodyState
from app.tools.es_client import get_es_client
from app.tools.embeddings import embed
from app.config import settings
import re
import logging
from typing import Optional
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

logger = logging.getLogger(__name__)


def _normalize_url(url: str) -> str:
    """Normalizes a URL by removing fragments, common tracking params, and ensuring consistent trailing slashes."""
    if not url:
        return ""

    parsed = urlparse(url)

    # Remove fragment
    path_without_fragment = parsed.path

    # Remove common tracking query parameters
    query_params = parse_qs(parsed.query)
    filtered_query_params = {
        k: v for k, v in query_params.items() if not k.startswith("utm_")
    }
    normalized_query = urlencode(filtered_query_params, doseq=True)

    # Reconstruct URL without fragment and with normalized query
    normalized_url = urlunparse(parsed._replace(query=normalized_query, fragment=""))

    # Ensure consistent trailing slashes (remove if not root or file)
    if (
        normalized_url.endswith("/")
        and len(path_without_fragment) > 1
        and "." not in path_without_fragment.split("/")[-1]
    ):
        normalized_url = normalized_url.rstrip("/")

    return normalized_url


def _norm(s: Optional[str]) -> str:
    """Normalize text by removing non-word characters and converting to lowercase"""
    return re.sub(r"\W+", " ", (s or "").lower()).strip()


def run(state: BodyState, es_client) -> BodyState:

    logger.info("Processing health query")
    if "user_query" not in state:
        raise ValueError("user_query is required in state")
    q = state["user_query"]
    logger.debug(f"Redacted query: {state.get('user_query_redacted', q)}")

    # Build a set of normalized ingredients from memory (e.g., {"ibuprofen", "warfarin"})
    mem_ings = set()
    logger.debug("Processing medical context from memory")
    for m in state.get("memory_facts") or []:
        ing = (m.get("normalized") or {}).get("ingredient") or _norm(m.get("name", ""))
        if ing:
            mem_ings.add(ing)
            logger.debug(f"Added medical context: {ing}")

    # Add memory terms to the query for retrieval context
    if mem_ings:
        q += "\nContext:" + ", ".join(sorted(mem_ings))
        logger.debug(f"Enhanced query with medical context: {q}")

    # k-NN first
    logger.info("Performing k-NN search for relevant medical knowledge")
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
    logger.debug("k-NN search parameters: k=8, candidates=64")

    try:
        res = get_es_client().search(index=settings.es_public_index, body=body_knn)
        hits = res["hits"]["hits"]
        logger.info(f"k-NN search found {len(hits)} relevant documents")
    except Exception as e:
        logger.error(f"k-NN search failed: {str(e)}", exc_info=True)
        hits = []

    # Fallback to BM25 if no k-NN hits (tiny corpora safety net)
    if not hits:
        logger.info("No k-NN hits, falling back to BM25 search")
        body_bm25 = {
            "query": {"multi_match": {"query": q, "fields": ["title^2", "text"]}},
            "_source": {"excludes": ["embedding"]},
            "size": 8,
        }
        try:
            res = get_es_client().search(index=settings.es_public_index, body=body_bm25)
            hits = res["hits"]["hits"]
            logger.info(f"BM25 search found {len(hits)} relevant documents")
        except Exception as e:
            logger.error(f"BM25 search failed: {str(e)}", exc_info=True)
            hits = []

    docs = [h["_source"] for h in hits]

    citations: list[str] = []
    alerts: list[str] = []
    messages: list[dict] = []

    # Build a memory ingredient set for generic interaction gating
    logger.info("Checking for medication interactions and warnings")
    med_mem_ings = set()
    for m in state.get("memory_facts") or []:
        if m.get("entity") == "medication":
            ing = (m.get("normalized") or {}).get("ingredient") or (
                m.get("name") or ""
            ).lower()
            if ing:
                med_mem_ings.add(ing)
                logger.debug(f"Found active medication: {ing}")
    logger.debug(f"Processing top {min(3, len(docs))} documents for alerts")
    for d in docs[:3]:
        section = (d.get("section", "") or "").lower()
        title = _norm(d.get("title"))
        text = _norm(d.get("text"))
        logger.debug(f"Analyzing document: {title} (section: {section})")

        add_alert = False
        if section == "warnings":
            add_alert = True
            logger.info(f"Found warning section in {title}")
        elif section == "interactions":
            # Only alert if >=2 distinct memory meds appear in the snippet
            found_meds = set()
            logger.debug("Checking for medication interactions")
            for ing in med_mem_ings:
                if ing and (ing in title or ing in text):
                    found_meds.add(ing)
                    logger.debug(f"Found interaction with: {ing}")
                if len(found_meds) >= 2:
                    add_alert = True
                    logger.warning(
                        f"Detected potential interaction between medications in {title}"
                    )
                    break

        if add_alert:
            alert = f"Check: {d.get('title')} — {d.get('section')}"
            alerts.append(alert)
            logger.warning(f"Added medical alert: {alert}")

        citation = _normalize_url(d.get("source_url", ""))
        citations.append(citation)
        logger.debug(f"Added citation: {citation}")

    if not messages:
        logger.info("No specific messages generated, adding default guidance message")
        default_message = {
            "role": "assistant",
            "content": "I found guidance and possible warnings. Review the summary and citations.",
        }
        messages.append(default_message)
        logger.debug(f"Added default message: {default_message}")

    logger.info(
        f"Health node processing complete. Generated {len(alerts)} alerts and {len(citations)} citations"
    )

    state["public_snippets"] = docs
    state["alerts"] = list(dict.fromkeys(alerts))
    # dedupe citations
    state["citations"] = list(dict.fromkeys(c for c in citations if c))
    state.setdefault("messages", []).extend(messages)
    return state
