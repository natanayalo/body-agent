from app.graph.nodes import planner
from app.graph.nodes.rationale_codes import (
    HOURS_MATCH,
    TRAVEL_WITHIN_LIMIT,
    PREFERRED_KIND,
    INSURANCE_MATCH,
)
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
            "insurance_plan": ["Maccabi", "Clalit"],
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
                    "Accepts your Maccabi insurance",
                ],
                "reason_codes": [
                    TRAVEL_WITHIN_LIMIT,
                    HOURS_MATCH,
                    PREFERRED_KIND,
                    INSURANCE_MATCH,
                ],
                "insurance_plans": ["maccabi", "leumit"],
                "matched_insurance_label": "Maccabi",
            }
        ],
    )

    new_state = planner.run(state)
    plan = new_state["plan"]
    assert plan["type"] == planner.APPOINTMENT_INTENT
    rationale = plan["rationale"]
    assert rationale.startswith("Because ")
    assert "4.2" in rationale
    assert "within your 5.0 km travel limit" in rationale
    assert "preferred morning hours" in rationale
    assert "matches your preferred clinic" in rationale
    assert "accepts your Maccabi insurance" in rationale
    assert plan["explanations"][0] == rationale
    assert plan["explanations"][1:] == state["candidates"][0]["reasons"]


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
            "insurance_plan": "מכבי",
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
                    "Accepts your מכבי insurance",
                ],
                "reason_codes": [TRAVEL_WITHIN_LIMIT, HOURS_MATCH, INSURANCE_MATCH],
                "insurance_plans": ["מכבי"],
                "matched_insurance_label": "מכבי",
            }
        ],
    )

    new_state = planner.run(state)
    plan = new_state["plan"]
    assert plan["type"] == planner.APPOINTMENT_INTENT
    rationale = plan["rationale"]
    assert rationale.startswith("כי ")
    assert 'מרחק של כ-2.5 ק"מ ממך' in rationale
    assert 'בתוך מגבלת הנסיעה של 3.0 ק"מ' in rationale
    assert "ערב" in rationale
    assert "מקבל את ביטוח מכבי שלך" in rationale
    assert plan["explanations"][0] == rationale


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
    assert plan["rationale"] == "Best match for your saved preferences."


def test_planner_rationale_insurance_uses_candidate_list():
    candidate = {
        "distance_km": 3.0,
        "kind": "clinic",
        "reason_codes": [TRAVEL_WITHIN_LIMIT, INSURANCE_MATCH],
        "insurance_plans": ["Clalit"],
        "matched_insurance_label": "Clalit",
    }
    prefs = {"max_travel_km": 5}

    rationale = planner._format_rationale("en", candidate, prefs)

    assert "it's about 3.0 km from you" in rationale
    assert "accepts your Clalit insurance" in rationale


def test_planner_rationale_insurance_prefers_pref_display():
    candidate = {
        "distance_km": None,
        "kind": "clinic",
        "reason_codes": [INSURANCE_MATCH],
        "insurance_plans": [],
    }
    prefs = {"insurance_plan": "Meuhedet"}

    rationale = planner._format_rationale("en", candidate, prefs)

    assert "Meuhedet" in rationale


def test_planner_rationale_insurance_pref_display_when_no_match():
    candidate = {
        "distance_km": None,
        "kind": "clinic",
        "reason_codes": [INSURANCE_MATCH],
        "insurance_plans": ["Meuhedet"],
    }
    prefs = {"insurance_plan": ["Leumit"]}

    rationale = planner._format_rationale("en", candidate, prefs)

    assert "Leumit" in rationale


def test_planner_rationale_travel_limit_only_phrase():
    candidate = {
        "reason_codes": [TRAVEL_WITHIN_LIMIT],
    }
    prefs = {"max_travel_km": 7}

    rationale = planner._format_rationale("en", candidate, prefs)

    assert rationale == "Because honors your 7.0 km travel limit."


def test_planner_rationale_handles_invalid_travel_limit():
    candidate = {
        "distance_km": 2.0,
        "reason_codes": [TRAVEL_WITHIN_LIMIT],
    }
    prefs = {"max_travel_km": "not-a-number"}

    rationale = planner._format_rationale("en", candidate, prefs)

    # Falls back to distance fragment without travel limit copy
    assert rationale.startswith("Because it's about 2.0 km from you")
    assert "travel limit" not in rationale
