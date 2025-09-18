from langgraph.graph import StateGraph, END
from app.graph.state import BodyState
from app.graph.nodes import (
    supervisor,
    scrub,
    memory,
    health,
    risk_ml,
    places,
    planner,
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


def build_graph():
    g = StateGraph(BodyState)
    g.add_node("supervisor", supervisor.run)
    g.add_node("scrub", scrub.run)
    g.add_node("memory", memory.run)
    g.add_node("health", health.run)
    g.add_node("risk_ml", risk_ml.run)
    g.add_node("places", places.run)
    g.add_node("planner", planner.run)
    g.add_node("critic", critic.run)

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
    # converge
    for n in ("risk_ml", "places", "planner"):
        g.add_edge(n, "critic")
    g.add_edge("critic", END)
    return g.compile()
