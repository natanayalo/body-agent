from typing import Dict, Tuple
from app.graph.state import BodyState
from app.tools.geo_tools import search_providers

# Dummy location for demo (Tel Aviv center). Replace with user-permitted geolocation
TLV = (32.0853, 34.7818)


def run(state: BodyState) -> BodyState:
    q = state.get("user_query", "")
    raw = search_providers(q, lat=TLV[0], lon=TLV[1], radius_km=10)
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
    return state
