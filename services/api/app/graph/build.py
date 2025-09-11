from langgraph.graph import StateGraph, END
from app.graph.state import BodyState
from app.graph.nodes import supervisor, memory, health, places, planner, critic
from app.graph.nodes import risk_ml
from app.graph.nodes import scrub


def _route_after_memory(state: BodyState) -> str:
    """Decide which expert to call after memory lookup based on intent."""
    intent = state.get("intent")
    if intent in ("meds", "symptom"):
        return "health"
    if intent == "appointment":
        return "places"
    return "planner"


def build_graph(es_client) -> StateGraph:
    """
    Construct a LangGraph StateGraph wiring existing node functions.

    Flow:
      START -> supervisor -> memory -> (health | places | planner) -> planner -> critic -> END
    """
    g = StateGraph(BodyState)

    # Register nodes
    g.add_node("scrub", scrub.run)
    g.add_node("supervisor", supervisor.run)
    g.add_node("memory", lambda state: memory.run(state, es_client))
    g.add_node("health", lambda state: health.run(state, es_client))
    g.add_node("places", lambda state: places.run(state, es_client))
    g.add_node("planner", lambda state: planner.run(state, es_client))
    g.add_node("critic", critic.run)
    g.add_node("risk_ml", risk_ml.run)

    # Entry & base edges
    g.set_entry_point("scrub")
    g.add_edge("scrub", "supervisor")
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
    # After health retrieval, run ML risk classifier, then plan
    g.add_edge("health", "risk_ml")
    g.add_edge("risk_ml", "planner")
    g.add_edge("places", "planner")
    g.add_edge("planner", "critic")
    g.add_edge("critic", END)

    return g
