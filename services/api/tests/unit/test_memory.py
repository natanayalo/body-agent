from unittest.mock import patch, MagicMock

from app.graph.nodes import memory
from app.graph.state import BodyState
from app.config import settings


def test_memory_run(fake_es, monkeypatch):
    """Test the memory node run function."""
    # Mock Elasticsearch result
    mock_search_return_value = {
        "hits": {
            "hits": [
                {"_source": {"name": "Ibuprofen 200mg", "entity": "medication"}},
                {"_source": {"name": "Ibuprofen 400mg", "entity": "medication"}},
                {"_source": {"name": "Aspirin 100mg", "entity": "medication"}},
            ]
        }
    }
    monkeypatch.setattr(
        fake_es, "search", MagicMock(return_value=mock_search_return_value)
    )

    # Force stub mode for this test
    monkeypatch.setattr(settings, "embeddings_model", "__stub__")

    # Initial state
    initial_state = BodyState(
        user_id="test-user",
        user_query="what meds am i on",
        user_query_redacted="what meds am i on",
        memory_facts=[],
    )

    # Run the memory node
    with patch("app.tools.embeddings.embed") as mock_embed:
        result_state = memory.run(initial_state)

    # Assertions for stub mode
    # In stub mode, embed should not be called, and it should use term query
    mock_embed.assert_not_called()
    search_body = fake_es.search.call_args.kwargs["body"]
    assert "knn" not in search_body
    assert search_body["query"]["term"]["user_id"] == "test-user"

    fake_es.search.assert_called_once()

    # Check that the results are deduplicated
    facts = result_state.get("memory_facts", [])
    assert len(facts) == 3
    fact_names = [fact["name"] for fact in facts]
    assert "Ibuprofen 200mg" in fact_names
    assert "Aspirin 100mg" in fact_names

    ingredients = {fact.get("normalized", {}).get("ingredient") for fact in facts}
    assert {"ibuprofen", "aspirin"}.issubset(ingredients)


def test_extract_preferences_builds_object():
    facts = [
        {"entity": "preference", "name": "preferred_kinds", "value": "lab,clinic"},
        {"entity": "preference", "name": "preferred_hours", "value": "Morning"},
        {"entity": "preference", "name": "max_distance_km", "value": "7.5"},
        {"entity": "preference", "name": "insurance_plan", "value": "maccabi"},
    ]

    prefs = memory.extract_preferences(facts)
    assert prefs["preferred_kinds"] == ["lab", "clinic"]
    assert prefs["hours_window"] == "morning"
    assert prefs["max_distance_km"] == 7.5
    assert prefs["insurance_plan"] == "maccabi"


def test_extract_preferences_ignores_empty_values():
    facts = [
        {"entity": "preference", "name": "preferred_kind", "value": ""},
        {"entity": "preference", "name": "max_distance_km", "value": "not_a_number"},
        {"entity": "note", "name": "foo", "value": "bar"},
        {"entity": "preference", "name": None, "value": "lab"},
    ]

    prefs = memory.extract_preferences(facts)
    assert prefs == {}


def test_extract_preferences_handles_non_string_values():
    facts = [
        {"entity": "preference", "name": "preferred_kinds", "value": ["Lab", "Clinic"]},
        {"entity": "preference", "name": "preferred_hours", "value": ["Evening"]},
        {"entity": "preference", "name": "max_distance_km", "value": 5},
    ]

    prefs = memory.extract_preferences(facts)
    assert prefs["preferred_kinds"] == ["lab", "clinic"]
    assert prefs["hours_window"] == "evening"
    assert prefs["max_distance_km"] == 5.0


def test_memory_run_sets_preferences(fake_es, monkeypatch):
    response = {
        "hits": {
            "hits": [
                {
                    "_source": {
                        "user_id": "demo",
                        "entity": "preference",
                        "name": "preferred_kinds",
                        "value": "lab",
                    }
                },
                {
                    "_source": {
                        "user_id": "demo",
                        "entity": "preference",
                        "name": "max_distance_km",
                        "value": "5",
                    }
                },
            ]
        }
    }
    monkeypatch.setattr(fake_es, "search", MagicMock(return_value=response))
    monkeypatch.setattr(settings, "embeddings_model", "__stub__")

    state = BodyState(
        user_id="demo",
        user_query="find lab",
        user_query_redacted="find lab",
    )

    with patch("app.tools.embeddings.embed") as mock_embed:
        result = memory.run(state, es_client=fake_es)

    mock_embed.assert_not_called()
    assert result.get("preferences", {}).get("preferred_kinds") == ["lab"]
    assert result["preferences"].get("max_distance_km") == 5.0
