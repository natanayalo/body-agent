from app.graph.nodes import supervisor, planner
from app.graph.state import BodyState


def test_supervisor_embedding_intents(fake_embed):
    s = {"user_query": "Please book me a lab appointment"}
    assert supervisor.detect_intent(s["user_query"]) in {"appointment", "other"}
    s2 = {"user_query": "יש לי חום"}
    assert supervisor.detect_intent(s2["user_query"]) in {"symptom", "other"}


def test_planner_preferences_ranking(fake_es):
    # Provide preferences via ES (entity=preference)
    def pred_prefs(idx, body):
        return idx.endswith("private_user_memory") and body.get("query", {}).get("bool")

    fake_es.add_handler(
        pred_prefs,
        {
            "hits": {
                "hits": [
                    {
                        "_source": {
                            "user_id": "demo-user",
                            "entity": "preference",
                            "name": "preferred_hours",
                            "value": "morning",
                        }
                    },
                    {
                        "_source": {
                            "user_id": "demo-user",
                            "entity": "preference",
                            "name": "preferred_kind",
                            "value": "lab",
                        }
                    },
                ]
            }
        },
    )

    state = BodyState(
        intent="appointment",
        user_id="demo-user",
        user_query="test query",  # Added user_query
        candidates=[
            {"name": "Clinic A", "kind": "clinic", "hours": "Sun-Thu 12:00-20:00"},
            {
                "name": "Dizengoff Lab Center",
                "kind": "lab",
                "hours": "Sun-Fri 07:00-14:00",
            },
        ],
    )
    out = planner.run(state, fake_es)
    plan = out.get("plan", {})
    assert plan.get("type") == "appointment"
    assert plan.get("provider", {}).get("name") == "Dizengoff Lab Center"
    assert "morning" in plan.get("reasons", "") or "preferred kind" in plan.get(
        "reasons", ""
    )


def test_planner_meds_intent(fake_es):
    state = BodyState(intent="meds", user_query="I need meds", messages=[])
    out = planner.run(state, fake_es)
    plan = out.get("plan", {})
    assert plan.get("type") == "med_schedule"
    assert len(plan.get("items", [])) == 2


def test_planner_appointment_no_candidates(fake_es):
    fake_es.add_handler(
        lambda i, b: i.endswith("private_user_memory"), {"hits": {"hits": []}}
    )
    state = BodyState(
        intent="appointment",
        user_id="demo-user",
        user_query="book appointment",
        candidates=[],
    )
    out = planner.run(state, fake_es)
    assert out.get("plan", {}).get("type") == "none"


def test_planner_appointment_no_preferences(fake_es):
    fake_es.add_handler(
        lambda i, b: i.endswith("private_user_memory"), {"hits": {"hits": []}}
    )
    state = BodyState(
        intent="appointment",
        user_id="demo-user",
        user_query="book appointment",
        candidates=[
            {"name": "Clinic A", "kind": "clinic", "hours": "Sun-Thu 12:00-20:00"}
        ],
    )
    out = planner.run(state, fake_es)
    plan = out.get("plan", {})
    assert plan.get("type") == "appointment"
    assert plan.get("provider", {}).get("name") == "Clinic A"
    assert plan.get("reasons") == ""


def test_planner_fallback_intent(fake_es):
    state = BodyState(intent="other", user_query="What is the weather?", messages=[])
    out = planner.run(state, fake_es)
    assert out.get("plan", {}).get("type") == "none"


def test_planner_appointment_no_user_id(fake_es):
    state = BodyState(
        intent="appointment",
        user_query="book appointment",
        candidates=[
            {"name": "Clinic A", "kind": "clinic", "hours": "Sun-Thu 12:00-20:00"}
        ],
    )
    out = planner.run(state, fake_es)
    plan = out.get("plan", {})
    assert plan.get("type") == "appointment"
    assert plan.get("provider", {}).get("name") == "Clinic A"
    assert plan.get("reasons") == ""


def test_planner_appointment_user_id_no_prefs(fake_es):
    fake_es.add_handler(
        lambda i, b: i.endswith("private_user_memory"), {"hits": {"hits": []}}
    )
    state = BodyState(
        intent="appointment",
        user_id="test-user",  # user_id is present
        user_query="book appointment",
        candidates=[
            {"name": "Clinic A", "kind": "clinic", "hours": "Sun-Thu 12:00-20:00"}
        ],
    )
    out = planner.run(state, fake_es)
    plan = out.get("plan", {})
    assert plan.get("type") == "appointment"
    assert plan.get("provider", {}).get("name") == "Clinic A"
    assert plan.get("reasons") == ""


def test_planner_appointment_candidate_no_hours(fake_es):
    fake_es.add_handler(
        lambda i, b: i.endswith("private_user_memory"),
        {
            "hits": {
                "hits": [
                    {
                        "_source": {
                            "user_id": "test-user",
                            "entity": "preference",
                            "name": "preferred_hours",
                            "value": "morning",
                        }
                    }
                ]
            }
        },
    )
    state = BodyState(
        intent="appointment",
        user_id="test-user",
        user_query="book appointment",
        candidates=[
            {"name": "Clinic A", "kind": "clinic", "hours": ""},  # Empty hours
            {"name": "Clinic B", "kind": "clinic", "hours": None},  # None hours
        ],
    )
    out = planner.run(state, fake_es)
    plan = out.get("plan", {})
    assert plan.get("type") == "appointment"
    assert plan.get("provider", {}).get("name") in ["Clinic A", "Clinic B"]
    assert plan.get("reasons") == ""
