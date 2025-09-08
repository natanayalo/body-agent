from unittest.mock import patch
from app.graph.nodes import memory
from app.graph.state import BodyState


def test_base_name():
    """Test the _base_name function."""
    assert memory._base_name("Ibuprofen 200mg") == "ibuprofen"
    assert memory._base_name("Aspirin 100 mg") == "aspirin"
    assert memory._base_name("Tylenol 500mcg") == "tylenol"
    assert memory._base_name("Cough Syrup 10ml") == "cough syrup"
    assert memory._base_name("  Vitamin C ") == "vitamin c"


@patch("app.graph.nodes.memory.embed", return_value=[[0.1, 0.2, 0.3]])
@patch("app.graph.nodes.memory.es")
def test_memory_run(mock_es, mock_embed):
    """Test the memory node run function."""
    # Mock Elasticsearch result
    mock_es.search.return_value = {
        "hits": {
            "hits": [
                {"_source": {"name": "Ibuprofen 200mg", "entity": "medication"}},
                {"_source": {"name": "Ibuprofen 400mg", "entity": "medication"}},
                {"_source": {"name": "Aspirin 100mg", "entity": "medication"}},
            ]
        }
    }

    # Initial state
    initial_state = BodyState(user_query="what meds am i on", memory_facts=[])

    # Run the memory node
    result_state = memory.run(initial_state)

    # Assertions
    mock_embed.assert_called_once_with(["what meds am i on"])
    mock_es.search.assert_called_once()

    # Check that the results are deduplicated
    assert len(result_state["memory_facts"]) == 2
    fact_names = [fact["name"] for fact in result_state["memory_facts"]]
    assert "Ibuprofen 200mg" in fact_names
    assert "Aspirin 100mg" in fact_names
