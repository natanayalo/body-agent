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


def test_planner_appointment_rationale_en(monkeypatch):
    monkeypatch.setattr(planner, "create_event", lambda event: "/tmp/mock.ics")
    state = BodyState(
        intent=planner.APPOINTMENT_INTENT,
        user_query="book appointment",
        user_query_redacted="book appointment",
        language="en",
        preferences={
            "max_travel_km": 5,
            "hours_window": "morning",
            "preferred_kinds": ["clinic"],
        },
        candidates=[
            {
                "name": "Morning Clinic",
                "distance_km": 4.2,
                "kind": "clinic",
                "reasons": [
                    "~4.2 km away",
                    "Within your 5 km travel limit",
                    "Open during morning",
                ],
            }
        ],
    )

    new_state = planner.run(state)
    plan = new_state["plan"]
    assert plan["type"] == planner.APPOINTMENT_INTENT
    assert plan["rationale"].startswith("Because")
    assert "4.2 km" in plan["rationale"]
    assert "morning" in plan["rationale"]
    assert plan["explanations"][0] == plan["rationale"]


def test_planner_appointment_rationale_he(monkeypatch):
    monkeypatch.setattr(planner, "create_event", lambda event: "/tmp/mock.ics")
    state = BodyState(
        intent=planner.APPOINTMENT_INTENT,
        user_query="קבע תור",
        user_query_redacted="קבע תור",
        language="he",
        preferences={
            "max_travel_km": 3,
            "hours_window": "evening",
        },
        candidates=[
            {
                "name": "Evening Clinic",
                "distance_km": 2.5,
                "kind": "clinic",
                "reasons": [
                    "~2.5 km away",
                    "Within your 3 km travel limit",
                    "Open during evening",
                ],
            }
        ],
    )

    new_state = planner.run(state)
    plan = new_state["plan"]
    assert plan["type"] == planner.APPOINTMENT_INTENT
    assert plan["rationale"].startswith("כי")
    assert 'ק"מ' in plan["rationale"]
    assert "ערב" in plan["rationale"]


def test_planner_appointment_rationale_default(monkeypatch):
    monkeypatch.setattr(planner, "create_event", lambda event: "/tmp/mock.ics")
    state = BodyState(
        intent=planner.APPOINTMENT_INTENT,
        user_query="book appointment",
        user_query_redacted="book appointment",
        language="en",
        candidates=[
            {
                "name": "Clinic",
                "reasons": [],
            }
        ],
    )

    new_state = planner.run(state)
    plan = new_state["plan"]
    assert plan["type"] == planner.APPOINTMENT_INTENT
    assert plan["rationale"].startswith("Best match")
