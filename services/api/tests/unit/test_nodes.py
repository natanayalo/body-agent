from app.graph.nodes import health, planner, risk_ml
from app.graph.state import BodyState


def test_health_node_with_med_terms():
    state: BodyState = {
        "user_query": "",
        "user_query_redacted": "",
        "memory_facts": [
            {
                "entity": "medication",
                "name": "ibuprofen 200mg",
                "normalized": {"ingredient": "ibuprofen"},
            },
            {
                "entity": "medication",
                "name": "warfarin 5mg",
                "normalized": {"ingredient": "warfarin"},
            },
        ],
    }

    # Mock ES client
    class MockEsClient:
        def search(self, index, body):
            return {
                "hits": {
                    "hits": [
                        {
                            "_source": {
                                "title": "Ibuprofen Warnings",
                                "section": "warnings",
                                "source_url": "http://example.com/ibuprofen",
                            }
                        },
                        {
                            "_source": {
                                "title": "Warfarin Interactions",
                                "section": "interactions",
                                "text": "ibuprofen and warfarin interaction",
                                "source_url": "http://example.com/warfarin",
                            }
                        },
                    ]
                }
            }

    new_state = health.run(state, es_client=MockEsClient())
    assert len(new_state["public_snippets"]) == 2
    assert len(new_state["alerts"]) == 2
    assert len(new_state["citations"]) == 2


def test_planner_node_meds_intent():
    state: BodyState = {"user_query": "", "user_query_redacted": "", "intent": "meds"}
    new_state = planner.run(state)
    assert new_state["plan"]["type"] == "med_schedule"


def test_planner_node_appointment_intent():
    state: BodyState = {
        "user_query": "",
        "user_query_redacted": "",
        "intent": "appointment",
        "candidates": [
            {"name": "Clinic A", "phone": "123", "kind": "clinic"},
            {"name": "Clinic B", "phone": "456", "kind": "lab"},
        ],
    }
    new_state = planner.run(state)
    assert new_state["plan"]["type"] == "appointment"
    assert new_state["plan"]["provider"]["name"] == "Clinic A"


def test_risk_ml_node_urgent_care():
    state: BodyState = {
        "user_query": "I have chest pain",
        "user_query_redacted": "I have chest pain",
    }
    new_state = risk_ml.run(state)
    assert any("urgent_care" in alert for alert in new_state["alerts"])
