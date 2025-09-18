from app.graph.build import _route_after_memory
from app.graph.state import BodyState


def test_route_after_memory_to_health():
    s: BodyState = {"intent": "symptom", "user_query": "x"}
    assert _route_after_memory(s) == "health"
    s = {"intent": "meds", "user_query": "x"}
    assert _route_after_memory(s) == "health"


def test_route_after_memory_to_places():
    s: BodyState = {"intent": "appointment", "user_query": "x"}
    assert _route_after_memory(s) == "places"


def test_route_after_memory_to_planner_default():
    # Unknown or missing intents safely fall back to planner
    s: BodyState = {"intent": "routine", "user_query": "x"}
    assert _route_after_memory(s) == "planner"
    s = {"user_query": "x"}  # no intent key
    assert _route_after_memory(s) == "planner"
