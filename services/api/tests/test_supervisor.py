import os
import json
import pytest
from unittest.mock import MagicMock
from app.graph.nodes import supervisor


# Mock the os.path.exists and json.load for _load_exemplars tests
@pytest.fixture
def mock_load_exemplars_deps(monkeypatch):
    mock_exists = MagicMock()
    mock_json_load = MagicMock()
    monkeypatch.setattr(os.path, "exists", mock_exists)
    monkeypatch.setattr(json, "load", mock_json_load)
    yield mock_exists, mock_json_load


def test_load_exemplars_from_file_success(monkeypatch, mock_load_exemplars_deps):
    mock_exists, mock_json_load = mock_load_exemplars_deps
    mock_exists.return_value = True
    mock_json_load.return_value = {
        "symptom": ["test symptom"],
        "meds": ["test meds"],
        "appointment": ["test appointment"],
        "routine": ["test routine"],
        "unknown": ["unknown intent"],  # Should be filtered out
    }
    monkeypatch.setenv("INTENT_EXEMPLARS_PATH", "/tmp/test_exemplars.json")

    # Mock builtins.open to simulate reading from the file
    from unittest.mock import mock_open

    mock_file_content = json.dumps(mock_json_load.return_value)
    mock_file = mock_open(read_data=mock_file_content)
    monkeypatch.setattr("builtins.open", mock_file)

    # Reload the module to re-run _load_exemplars
    import importlib

    importlib.reload(supervisor)

    exemplars = supervisor._EXEMPLARS
    assert "symptom" in exemplars
    assert "test symptom" in exemplars["symptom"]
    assert "unknown" not in exemplars  # Ensure unknown intents are filtered


def test_load_exemplars_from_file_malformed(monkeypatch, mock_load_exemplars_deps):
    mock_exists, mock_json_load = mock_load_exemplars_deps
    mock_exists.return_value = True
    mock_json_load.side_effect = json.JSONDecodeError(
        "malformed", "doc", 0
    )  # Simulate malformed JSON
    monkeypatch.setenv("INTENT_EXEMPLARS_PATH", "/tmp/malformed_exemplars.json")

    # Reload the module to re-run _load_exemplars
    import importlib

    importlib.reload(supervisor)

    exemplars = supervisor._EXEMPLARS
    assert exemplars == supervisor._DEFAULT_EXAMPLES  # Should fall back to default


def test_load_exemplars_from_file_non_existent(monkeypatch, mock_load_exemplars_deps):
    mock_exists, _ = mock_load_exemplars_deps
    mock_exists.return_value = False  # Simulate non-existent file
    monkeypatch.setenv("INTENT_EXEMPLARS_PATH", "/tmp/non_existent_exemplars.json")

    # Reload the module to re-run _load_exemplars
    import importlib

    importlib.reload(supervisor)

    exemplars = supervisor._EXEMPLARS
    assert exemplars == supervisor._DEFAULT_EXAMPLES  # Should fall back to default


def test_detect_intent_returns_other_if_no_match(fake_embed):
    # Set up fake_embed to return all zeros for all inputs
    # This will make all scores 0.0
    fake_embed.return_value = [0.0, 0.0, 0.0]

    # Temporarily set thresholds to ensure no match
    original_threshold = supervisor._THRESHOLD
    original_margin = supervisor._MARGIN
    supervisor._THRESHOLD = 1.0  # High threshold
    supervisor._MARGIN = 1.0  # High margin

    # Reload supervisor to apply new thresholds
    import importlib

    importlib.reload(supervisor)

    intent = supervisor.detect_intent("This is a completely unrelated query")
    assert intent == "other"

    # Restore original thresholds
    supervisor._THRESHOLD = original_threshold
    supervisor._MARGIN = original_margin
    importlib.reload(supervisor)  # Reload to restore original values
