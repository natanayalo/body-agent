from app.graph.nodes import supervisor, planner


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

    state = {
        "intent": "appointment",
        "user_id": "demo-user",
        "candidates": [
            {"name": "Clinic A", "kind": "clinic", "hours": "Sun-Thu 12:00-20:00"},
            {
                "name": "Dizengoff Lab Center",
                "kind": "lab",
                "hours": "Sun-Fri 07:00-14:00",
            },
        ],
    }
    out = planner.run(state)
    plan = out.get("plan", {})
    assert plan.get("type") == "appointment"
    assert plan.get("provider", {}).get("name") == "Dizengoff Lab Center"
    assert "morning" in plan.get("reasons", "") or "preferred kind" in plan.get(
        "reasons", ""
    )
