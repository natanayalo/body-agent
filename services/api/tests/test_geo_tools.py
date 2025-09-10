from unittest.mock import patch
from app.tools import geo_tools


@patch("app.tools.geo_tools.embed", return_value=[[0.1, 0.2, 0.3]])
@patch("app.tools.geo_tools.es")
def test_search_providers_with_geo(mock_es, mock_embed):
    """Test search_providers with geo-location."""
    # Mock Elasticsearch result
    mock_es.search.return_value = {
        "hits": {
            "hits": [
                {"_source": {"name": "Provider A"}, "_score": 0.9},
            ]
        }
    }

    # Call the function
    result = geo_tools.search_providers("test query", lat=1.0, lon=2.0)

    # Assertions
    mock_embed.assert_called_once_with(["test query"])
    mock_es.search.assert_called_once()
    args, kwargs = mock_es.search.call_args
    assert "geo_distance" in kwargs["body"]["query"]["bool"]["must"][0]
    assert result[0]["name"] == "Provider A"


@patch("app.tools.geo_tools.embed", return_value=[[0.1, 0.2, 0.3]])
@patch("app.tools.geo_tools.es")
def test_search_providers_without_geo(mock_es, mock_embed):
    """Test search_providers without geo-location."""
    # Mock Elasticsearch result
    mock_es.search.return_value = {
        "hits": {
            "hits": [
                {"_source": {"name": "Provider B"}, "_score": 0.8},
            ]
        }
    }

    # Call the function
    result = geo_tools.search_providers("test query")

    # Assertions
    mock_embed.assert_called_once_with(["test query"])
    mock_es.search.assert_called_once()
    args, kwargs = mock_es.search.call_args
    assert kwargs["body"]["query"] == {"match_all": {}}
    assert result[0]["name"] == "Provider B"
