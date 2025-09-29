from app.graph.nodes import planner
from app.graph.state import BodyState
from datetime import datetime, UTC


def test_planner_meds_schedule_sub_intent():
    """Planner keeps schedule only when meds sub_intent is 'schedule'."""
    state = BodyState(
        user_id="test-user",
        user_query="schedule my meds",
        intent=planner.MEDS_INTENT,
        sub_intent=planner.SUB_INTENT_SCHEDULE,
    )

    # We don't need a real ES client for this test
    es_client = None

    new_state = planner.run(state, es_client)

    assert "plan" in new_state
    plan = new_state["plan"]
    assert plan["type"] == planner.PLAN_TYPE_MED_SCHEDULE
    assert len(plan["items"]) == 2

    now = datetime.now(UTC)
    item1 = plan["items"][0]
    assert item1["title"] == "Morning meds"
    assert datetime.fromisoformat(item1["time"]) > now

    item2 = plan["items"][1]
    assert item2["title"] == "Evening meds"
    assert datetime.fromisoformat(item2["time"]) > datetime.fromisoformat(item1["time"])


def test_planner_meds_non_schedule_gets_none_plan():
    state = BodyState(
        intent=planner.MEDS_INTENT,
        sub_intent="onset",
        user_query="when does it work",
    )

    new_state = planner.run(state)

    assert new_state["plan"] == {"type": planner.PLAN_TYPE_NONE}
