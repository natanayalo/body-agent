from app.graph.build import _route_after_memory
from app.graph.state import BodyState


def test_route_after_memory_to_health():
    state = BodyState(intent="symptom", user_query="test")
    assert _route_after_memory(state) == "health"

    state = BodyState(intent="meds", user_query="test")
    assert _route_after_memory(state) == "health"


def test_route_after_memory_to_places():
    state = BodyState(intent="appointment", user_query="test")
    assert _route_after_memory(state) == "places"


def test_route_after_memory_to_planner():
    state = BodyState(intent="other", user_query="test")
    assert _route_after_memory(state) == "planner"

    state = BodyState(intent="routine", user_query="test")
    assert _route_after_memory(state) == "planner"

    state = BodyState(intent=None, user_query="test")
    assert _route_after_memory(state) == "planner"
