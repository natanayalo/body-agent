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
    assert len(result_state.get("memory_facts", [])) == 3
    fact_names = [fact["name"] for fact in result_state.get("memory_facts", [])]
    assert "Ibuprofen 200mg" in fact_names
    assert "Aspirin 100mg" in fact_names
