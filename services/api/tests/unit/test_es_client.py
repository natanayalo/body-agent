import pytest
from elastic_transport import ConnectionError
from unittest.mock import MagicMock
from app.tools import es_client  # Import the module itself


def test_get_es_client_initialization(monkeypatch):
    """Test that get_es_client initializes the client and ensures indices."""
    mock_elasticsearch = MagicMock()

    monkeypatch.setattr(es_client, "Elasticsearch", mock_elasticsearch)

    # Reset the singleton before the test
    es_client._es_client = None

    # First call: _es_client should be None, so it initializes
    client1 = es_client.get_es_client()
    mock_elasticsearch.assert_called_once()
    assert client1 == mock_elasticsearch.return_value

    # Second call: _es_client should already be initialized, so it returns existing client
    client2 = es_client.get_es_client()
    mock_elasticsearch.assert_called_once()  # Should not be called again
    assert client2 == client1


def test_ensure_indices_creates_missing_es_client_direct(monkeypatch):
    """Test ensure_indices directly with a mock Elasticsearch client."""
    mock_es_client = MagicMock()
    mock_es_client.indices.exists.side_effect = [False, False, False]

    monkeypatch.setattr(es_client, "get_es_client", lambda: mock_es_client)

    es_client.ensure_indices()
    assert mock_es_client.indices.create.call_count == 3


def test_ensure_indices_does_not_create_existing_es_client_direct(monkeypatch):
    """Test ensure_indices directly with a mock Elasticsearch client."""
    mock_es_client = MagicMock()
    mock_es_client.indices.exists.side_effect = [True, True, True]

    monkeypatch.setattr(es_client, "get_es_client", lambda: mock_es_client)

    es_client.ensure_indices()
    assert mock_es_client.indices.create.call_count == 0


def test_get_es_client_retry_and_succeed(monkeypatch):
    """Test that get_es_client retries on ConnectionError and eventually succeeds."""
    mock_es_class = MagicMock()
    mock_es_instance = MagicMock()
    # Fail twice, then succeed
    mock_es_class.side_effect = [
        ConnectionError("fail1"),
        ConnectionError("fail2"),
        mock_es_instance,
    ]

    monkeypatch.setattr(es_client, "Elasticsearch", mock_es_class)
    monkeypatch.setattr(
        "app.tools.es_client.time.sleep", lambda s: None
    )  # Don't actually sleep

    # Reset the singleton
    es_client._es_client = None

    client = es_client.get_es_client()

    assert mock_es_class.call_count == 3
    assert client == mock_es_instance


def test_get_es_client_fails_after_retries(monkeypatch):
    """Test that get_es_client raises ConnectionError after all retries fail."""
    mock_es_class = MagicMock(side_effect=ConnectionError("persistent failure"))

    monkeypatch.setattr(es_client, "Elasticsearch", mock_es_class)
    monkeypatch.setattr("app.tools.es_client.time.sleep", lambda s: None)

    # Reset the singleton
    es_client._es_client = None

    with pytest.raises(ConnectionError, match="Connection error"):
        es_client.get_es_client()

    assert mock_es_class.call_count == 20
