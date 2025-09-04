from app.graph.state import BodyState
from app.tools.geo_tools import search_providers


# Dummy location for demo (Tel Aviv center). Replace with user-permitted geolocation
TLV = (32.0853, 34.7818)


def run(state: BodyState) -> BodyState:
    q = state["user_query"]
    candidates = search_providers(q, lat=TLV[0], lon=TLV[1], radius_km=10)
    state["candidates"] = candidates
    return state
