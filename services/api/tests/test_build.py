from app.graph.build import _route_after_memory
from app.graph.state import BodyState


def test_route_after_memory_to_health():
    state = BodyState(intent="symptom")
    assert _route_after_memory(state) == "health"

    state = BodyState(intent="meds")
    assert _route_after_memory(state) == "health"


def test_route_after_memory_to_places():
    state = BodyState(intent="appointment")
    assert _route_after_memory(state) == "places"


def test_route_after_memory_to_planner():
    state = BodyState(intent="other")
    assert _route_after_memory(state) == "planner"

    state = BodyState(intent="routine")
    assert _route_after_memory(state) == "planner"

    state = BodyState(intent=None)
    assert _route_after_memory(state) == "planner"
