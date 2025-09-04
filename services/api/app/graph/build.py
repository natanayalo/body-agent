from langgraph.graph import StateGraph, END
from app.graph.state import BodyState
from app.graph.nodes import supervisor, memory, health, places, planner, critic


def _route_after_memory(state: BodyState) -> str:
    """Decide which expert to call after memory lookup based on intent."""
    intent = state.get("intent")
    if intent in ("meds", "symptom"):
        return "health"
    if intent == "appointment":
        return "places"
    return "planner"


def build_graph() -> StateGraph:
    """
    Construct a LangGraph StateGraph wiring existing node functions.

    Flow:
      START -> supervisor -> memory -> (health | places | planner) -> planner -> critic -> END
    """
    g = StateGraph(BodyState)

    # Register nodes
    g.add_node("supervisor", supervisor.run)
    g.add_node("memory",     memory.run)
    g.add_node("health",     health.run)
    g.add_node("places",     places.run)
    g.add_node("planner",    planner.run)
    g.add_node("critic",     critic.run)

    # Entry & base edges
    g.set_entry_point("supervisor")
    g.add_edge("supervisor", "memory")

    # Conditional routing after memory
    g.add_conditional_edges(
        "memory",
        _route_after_memory,
        {
            "health": "health",
            "places": "places",
            "planner": "planner",
        },
    )

    # Converge to planner, then critic, then END
    g.add_edge("health", "planner")
    g.add_edge("places", "planner")
    g.add_edge("planner", "critic")
    g.add_edge("critic", END)

    return g
