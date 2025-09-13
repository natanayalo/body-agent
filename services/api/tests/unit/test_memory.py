from unittest.mock import patch, MagicMock
from app.graph.nodes import memory
from app.graph.state import BodyState
from app.config import settings


def test_base_name():
    """Test the _base_name function."""
    assert memory._base_name("Ibuprofen 200mg") == "ibuprofen"
    assert memory._base_name("Aspirin 100 mg") == "aspirin"
    assert memory._base_name("Tylenol 500mcg") == "tylenol"
    assert memory._base_name("Cough Syrup 10ml") == "cough syrup"
    assert memory._base_name("  Vitamin C ") == "vitamin c"


@patch("app.graph.nodes.memory.embed", return_value=[[0.1, 0.2, 0.3]])
def test_memory_run(mock_embed, fake_es, monkeypatch):
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

    # Initial state
    initial_state = BodyState(
        user_id="test-user",
        user_query="what meds am i on",
        user_query_redacted="what meds am i on",  # Add this line
        memory_facts=[],
    )

    # Run the memory node
    result_state = memory.run(initial_state, fake_es)

    # Assertions
    if settings.embeddings_model == "__stub__":
        mock_embed.assert_not_called()
        search_body = fake_es.search.call_args.kwargs["body"]
        assert "knn" not in search_body
        assert search_body["query"]["term"]["user_id"] == "test-user"
    else:
        mock_embed.assert_called_once_with(["what meds am i on"])
        search_body = fake_es.search.call_args.kwargs["body"]
        assert search_body["knn"]["filter"]["term"]["user_id"] == "test-user"

    fake_es.search.assert_called_once()

    # Check that the results are deduplicated
    assert len(result_state.get("memory_facts", [])) == 2
    fact_names = [fact["name"] for fact in result_state.get("memory_facts", [])]
    assert "Ibuprofen 200mg" in fact_names
    assert "Aspirin 100mg" in fact_names
