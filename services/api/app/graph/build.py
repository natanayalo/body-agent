from langgraph.graph import StateGraph, END
from time import perf_counter
from typing import Callable

from app.graph.state import BodyState
from app.graph.nodes import (
    supervisor,
    scrub,
    memory,
    health,
    risk_ml,
    places,
    planner,
    answer_gen,
    critic,
)


def _route_after_memory(state: BodyState) -> str:
    """Route to the appropriate node after memory lookup."""

    intent = state.get("intent")
    if intent in {"meds", "symptom"}:
        return "health"
    if intent == "appointment":
        return "places"
    return "planner"


def _wrap_node(
    name: str, fn: Callable[[BodyState], BodyState]
) -> Callable[[BodyState], BodyState]:
    def wrapped(state: BodyState) -> BodyState:
        start = perf_counter()
        result = fn(state)
        elapsed_ms = (perf_counter() - start) * 1000.0
        target = result if isinstance(result, dict) else state
        debug = target.setdefault("debug", {})
        trace = debug.setdefault("trace", [])
        trace.append({"node": name, "elapsed_ms": elapsed_ms})
        return result

    return wrapped


def build_graph():
    g = StateGraph(BodyState)
    g.add_node("supervisor", _wrap_node("supervisor", supervisor.run))
    g.add_node("scrub", _wrap_node("scrub", scrub.run))
    g.add_node("memory", _wrap_node("memory", memory.run))
    g.add_node("health", _wrap_node("health", health.run))
    g.add_node("risk_ml", _wrap_node("risk_ml", risk_ml.run))
    g.add_node("places", _wrap_node("places", places.run))
    g.add_node("planner", _wrap_node("planner", planner.run))
    g.add_node("answer_gen", _wrap_node("answer_gen", answer_gen.run))
    g.add_node("critic", _wrap_node("critic", critic.run))

    g.set_entry_point("scrub")
    g.add_edge("scrub", "supervisor")
    g.add_edge("supervisor", "memory")
    # branches
    g.add_conditional_edges(
        "memory",
        _route_after_memory,
        {
            "health": "health",
            "places": "places",
            "planner": "planner",
        },
    )
    g.add_edge("health", "risk_ml")
    # Converge via planner, then critic
    g.add_edge("risk_ml", "planner")
    g.add_edge("places", "planner")
    g.add_edge("planner", "answer_gen")
    g.add_edge("answer_gen", "critic")
    g.add_edge("critic", END)
    return g.compile()
