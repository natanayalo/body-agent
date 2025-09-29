from app.graph.nodes import supervisor, planner
from app.graph.state import BodyState


def test_supervisor_embedding_intents(fake_embed):
    s = {"user_query": "Please book me a lab appointment"}
    assert supervisor.detect_intent(s["user_query"]) in {"appointment", "other"}
    s2 = {"user_query": "יש לי חום"}
    assert supervisor.detect_intent(s2["user_query"]) in {"symptom", "other"}


def test_planner_preferences_ranking():
    state = BodyState(
        intent=planner.APPOINTMENT_INTENT,
        user_id="demo-user",
        user_query="book appointment",
        preferences={"preferred_kinds": ["lab"], "hours_window": "morning"},
        candidates=[
            {
                "name": "Dizengoff Lab Center",
                "kind": "lab",
                "hours": "Sun-Fri 07:00-14:00",
                "score": 0.8,
                "reasons": ["Matches preferred kind (lab)", "Open during morning"],
            },
            {
                "name": "Clinic A",
                "kind": "clinic",
                "hours": "Sun-Thu 12:00-20:00",
                "score": 0.4,
                "reasons": ["~0.6 km away"],
            },
        ],
    )
    out = planner.run(state)
    plan = out.get("plan", {})
    assert plan.get("type") == planner.APPOINTMENT_INTENT
    assert plan.get("provider", {}).get("name") == "Dizengoff Lab Center"
    explanations = plan.get("explanations", [])
    assert explanations
    assert any("preferred" in reason for reason in explanations)


def test_planner_meds_schedule_intent():
    state = BodyState(
        intent=planner.MEDS_INTENT,
        user_query="I need meds",
        messages=[],
        sub_intent=planner.SUB_INTENT_SCHEDULE,
    )
    out = planner.run(state)
    plan = out.get("plan", {})
    assert plan.get("type") == planner.PLAN_TYPE_MED_SCHEDULE
    assert len(plan.get("items", [])) == 2


def test_planner_meds_non_schedule_sub_intent():
    state = BodyState(
        intent=planner.MEDS_INTENT,
        user_query="when will it work",
        messages=[],
        sub_intent="onset",
    )
    out = planner.run(state)
    assert out.get("plan", {}) == {"type": planner.PLAN_TYPE_NONE}


def test_planner_appointment_no_candidates():
    state = BodyState(
        intent=planner.APPOINTMENT_INTENT,
        user_id="demo-user",
        user_query="book appointment",
        candidates=[],
    )
    out = planner.run(state)
    assert out.get("plan", {}).get("type") == planner.PLAN_TYPE_NONE


def test_planner_appointment_no_preferences():
    state = BodyState(
        intent=planner.APPOINTMENT_INTENT,
        user_id="demo-user",
        user_query="book appointment",
        candidates=[
            {"name": "Clinic A", "kind": "clinic", "hours": "Sun-Thu 12:00-20:00"}
        ],
    )
    out = planner.run(state)
    plan = out.get("plan", {})
    assert plan.get("type") == planner.APPOINTMENT_INTENT
    assert plan.get("provider", {}).get("name") == "Clinic A"
    assert plan.get("reasons") == ""
    assert plan.get("explanations", []) == []


def test_planner_fallback_intent():
    state = BodyState(intent="other", user_query="What is the weather?", messages=[])
    out = planner.run(state)
    assert out.get("plan", {}).get("type") == planner.PLAN_TYPE_NONE


def test_planner_appointment_no_user_id():
    state = BodyState(
        intent=planner.APPOINTMENT_INTENT,
        user_query="book appointment",
        candidates=[
            {"name": "Clinic A", "kind": "clinic", "hours": "Sun-Thu 12:00-20:00"}
        ],
    )
    out = planner.run(state)
    plan = out.get("plan", {})
    assert plan.get("type") == planner.APPOINTMENT_INTENT
    assert plan.get("provider", {}).get("name") == "Clinic A"
    assert plan.get("reasons") == ""
    assert plan.get("explanations", []) == []


def test_planner_appointment_user_id_no_prefs():
    state = BodyState(
        intent=planner.APPOINTMENT_INTENT,
        user_id="test-user",  # user_id is present
        user_query="book appointment",
        candidates=[
            {"name": "Clinic A", "kind": "clinic", "hours": "Sun-Thu 12:00-20:00"}
        ],
    )
    out = planner.run(state)
    plan = out.get("plan", {})
    assert plan.get("type") == planner.APPOINTMENT_INTENT
    assert plan.get("provider", {}).get("name") == "Clinic A"
    assert plan.get("reasons") == ""
    assert plan.get("explanations", []) == []


def test_planner_appointment_candidate_no_hours():
    state = BodyState(
        intent=planner.APPOINTMENT_INTENT,
        user_id="test-user",
        user_query="book appointment",
        candidates=[
            {"name": "Clinic A", "kind": "clinic", "hours": ""},  # Empty hours
            {"name": "Clinic B", "kind": "clinic", "hours": None},  # None hours
        ],
    )
    out = planner.run(state)
    plan = out.get("plan", {})
    assert plan.get("type") == planner.APPOINTMENT_INTENT
    assert plan.get("provider", {}).get("name") in ["Clinic A", "Clinic B"]
    assert plan.get("reasons") == ""
    assert plan.get("explanations", []) == []
