from typing import Dict, Tuple
from app.graph.state import BodyState
from app.tools.geo_tools import search_providers
import logging

logger = logging.getLogger(__name__)

# Dummy location for demo (Tel Aviv center). Replace with user-permitted geolocation
TLV = (32.0853, 34.7818)


def run(state: BodyState, es_client) -> BodyState:
    q = state.get("user_query_redacted", state.get("user_query", ""))
    logger.debug(f"Searching providers for query: {q}")
    raw = search_providers(es_client, q, lat=TLV[0], lon=TLV[1], radius_km=10)
    logger.debug(f"Raw provider search results: {raw}")
    # dedupe by (name, phone) keeping highest score
    best: Dict[Tuple[str, str], Dict] = {}
    for c in raw:
        name = c.get("name")
        phone = c.get("phone")
        if not name or not phone:
            continue
        key = (name, phone)
        if key not in best or c.get("_score", 0) > best[key].get("_score", 0):
            best[key] = c
    state["candidates"] = list(best.values())
    logger.debug(f"Final candidates after deduplication: {state['candidates']}")
    return state
