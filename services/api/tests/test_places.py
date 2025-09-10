from unittest.mock import patch
from app.graph.nodes import places
from app.graph.state import BodyState


def test_places_run():
    """Test the places node run function."""
    # Sample providers returned by the mocked search_providers
    sample_providers = [
        {"name": "Provider A", "phone": "123", "_score": 0.9},
        {"name": "Provider A", "phone": "123", "_score": 0.8},
        {"name": "Provider B", "phone": "456", "_score": 0.95},
        {"name": "Provider C", "phone": "789", "_score": 0.92},
    ]

    # Initial state
    initial_state = BodyState(user_query="find a doctor", candidates=[])

    # Patch the search_providers function
    with patch(
        "app.graph.nodes.places.search_providers", return_value=sample_providers
    ) as mock_search:
        # Run the places node
        result_state = places.run(initial_state)

        # Assert that search_providers was called
        mock_search.assert_called_once()

        # Assert that the candidates are deduplicated, keeping the one with the highest score
        assert len(result_state.get("candidates", [])) == 3
        candidates = result_state.get("candidates", [])
        # The provider with the highest score should be kept
        assert any(p["name"] == "Provider A" and p["_score"] == 0.9 for p in candidates)
        # The other providers should be present
        assert any(p["name"] == "Provider B" for p in candidates)
        assert any(p["name"] == "Provider C" for p in candidates)
