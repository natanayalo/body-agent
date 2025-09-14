from app.graph.nodes import planner
from app.graph.state import BodyState
from datetime import datetime, UTC


def test_planner_meds_intent():
    """Test that the planner creates a med schedule for the 'meds' intent."""
    state = BodyState(
        user_id="test-user",
        user_query="schedule my meds",
        intent="meds",
    )

    # We don't need a real ES client for this test
    es_client = None

    new_state = planner.run(state, es_client)

    assert "plan" in new_state
    plan = new_state["plan"]
    assert plan["type"] == "med_schedule"
    assert len(plan["items"]) == 2

    now = datetime.now(UTC)
    item1 = plan["items"][0]
    assert item1["title"] == "Morning meds"
    assert datetime.fromisoformat(item1["time"]) > now

    item2 = plan["items"][1]
    assert item2["title"] == "Evening meds"
    assert datetime.fromisoformat(item2["time"]) > datetime.fromisoformat(item1["time"])
