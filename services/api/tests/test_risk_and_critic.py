from unittest.mock import MagicMock, patch
import os
from app.graph.nodes import risk_ml, critic


def test_risk_ml_triggers_only_above_threshold(fake_pipe):
    # No trigger by default
    state = {"user_query": "I have a fever of 38.5C", "messages": []}
    out = risk_ml.run(state)
    assert "alerts" not in out or not any("ML risk" in a for a in out.get("alerts", []))

    # Trigger urgent_care
    fake_pipe.run(urgent_care=0.8, see_doctor=0.3, self_care=0.2, info_only=0.0)
    out2 = risk_ml.run({"user_query": "Chest pain and shortness of breath"})
    assert any("ML risk: urgent_care" in a for a in out2.get("alerts", []))


def test_critic_banner_gated_by_ml(fake_pipe):
    # No ML triggers → critic should NOT add red-flag banner
    state = {
        "user_query": "I have a mild fever",
        "public_snippets": [{"section": "general"}],
        "citations": ["x"],
    }
    out = critic.run(risk_ml.run(state))
    assert not any("Potential red-flag" in a for a in out.get("alerts", []))

    # ML urgent care → critic should add banner
    fake_pipe.run(urgent_care=0.7, see_doctor=0.1, self_care=0.1, info_only=0.1)
    state2 = {
        "user_query": "Severe chest pain",
        "public_snippets": [{"section": "general"}],
        "citations": ["x"],
    }
    out2 = critic.run(risk_ml.run(state2))
    assert any("Potential red-flag" in a for a in out2.get("alerts", []))

    # ML urgent care and see_doctor -> critic should add banner only once
    fake_pipe.run(urgent_care=0.7, see_doctor=0.7, self_care=0.1, info_only=0.1)
    state3 = {
        "user_query": "Severe chest pain and high fever",
        "public_snippets": [{"section": "general"}],
        "citations": ["x"],
    }
    out3 = critic.run(risk_ml.run(state3))
    assert (
        out3.get("alerts", []).count(
            "Potential red-flag detected. Consider urgent care if symptoms worsen."
        )
        == 1
    )


def test_risk_ml_no_pipe(monkeypatch):
    # Test that the node returns the state as-is if the ML pipeline can't be loaded.
    monkeypatch.setattr(risk_ml, "_get_pipe", lambda: None)
    state = {"user_query": "I have a headache"}
    out = risk_ml.run(state)
    assert out == state


def test_risk_ml_with_med_context(monkeypatch):
    # Test that medication context is added to the text passed to the pipeline.
    mock_pipe = MagicMock()
    mock_pipe.return_value = {"labels": [], "scores": []}
    monkeypatch.setattr(risk_ml, "_get_pipe", lambda: mock_pipe)
    state = {
        "user_query": "Is it safe to take this?",
        "memory_facts": [
            {"entity": "medication", "name": "Ibuprofen 200mg"},
            {"entity": "condition", "name": "headache"},
        ],
    }
    risk_ml.run(state)
    mock_pipe.assert_called_once()
    call_args, _ = mock_pipe.call_args
    assert "Ibuprofen 200mg" in call_args[0]


def test_risk_ml_gentle_guidance(monkeypatch):
    # Test the "gentle guidance" feature where the top-scoring label is used if no threshold is met.
    mock_pipe = MagicMock()
    mock_pipe.return_value = {
        "labels": ["urgent_care", "see_doctor", "self_care", "info_only"],
        "scores": [0.4, 0.3, 0.2, 0.1],
    }
    monkeypatch.setattr(risk_ml, "_get_pipe", lambda: mock_pipe)
    state = {"user_query": "I have a slight cough", "messages": []}
    out = risk_ml.run(state)
    assert "messages" in out
    assert len(out["messages"]) == 1
    assert "Potential urgent issue" in out["messages"][0]["content"]


def test_parse_thresholds():
    # Test the _parse_thresholds function with various inputs.
    assert risk_ml._parse_thresholds("urgent_care:0.8, see_doctor:0.6") == {
        "urgent_care": 0.8,
        "see_doctor": 0.6,
    }
    assert risk_ml._parse_thresholds("invalid-spec") == {}
    assert risk_ml._parse_thresholds("") == {}
    assert risk_ml._parse_thresholds("urgent_care:0.8, invalid, see_doctor:0.6") == {
        "urgent_care": 0.8,
        "see_doctor": 0.6,
    }
    assert risk_ml._parse_thresholds("urgent_care:invalid") == {}


def test_risk_ml_pipe_exception(monkeypatch):
    # Test that the node handles exceptions from the pipeline gracefully.
    mock_pipe = MagicMock()
    mock_pipe.side_effect = Exception("Pipeline error")
    monkeypatch.setattr(risk_ml, "_get_pipe", lambda: mock_pipe)
    state = {"user_query": "This will cause an error"}
    out = risk_ml.run(state)
    assert out == state


def test_risk_ml_no_labels(monkeypatch):
    # Test that the node returns the state as-is if no risk labels are configured.
    monkeypatch.setenv("RISK_LABELS", "")
    state = {"user_query": "I have a question"}
    out = risk_ml.run(state)
    assert out == state


def test_critic_no_citations_alert():
    state = {
        "user_query": "Some query",
        "public_snippets": [{"title": "Doc1"}],
        "citations": [],  # No citations
    }
    out = critic.run(state)
    assert "alerts" in out
    assert "No citations found; verify guidance." in out["alerts"]


@patch.dict(os.environ, {"RISK_MODEL_ID": "non-existent-model"})
def test_risk_ml_get_pipe_exception():
    # This test will try to load a non-existent model, triggering the exception
    # The _PIPE should be None after this.
    risk_ml._PIPE = None  # Reset global pipe
    pipe = risk_ml._get_pipe()
    assert pipe is None


@patch.dict(os.environ, {"RISK_THRESHOLDS": "urgent_care:invalid_value"})
def test_risk_ml_parse_thresholds_value_error():
    # This test will provide an invalid threshold value, triggering the ValueError
    thresholds = risk_ml._parse_thresholds(os.environ["RISK_THRESHOLDS"])
    assert thresholds == {}


def test_risk_ml_score_below_threshold(fake_pipe):
    # Set scores below threshold
    fake_pipe.run(urgent_care=0.1, see_doctor=0.1, self_care=0.1, info_only=0.1)
    state = {"user_query": "I am fine", "messages": []}
    out = risk_ml.run(state)
    assert "alerts" not in out or not any("ML risk" in a for a in out.get("alerts", []))
    assert "messages" in out
    assert len(out["messages"]) == 1  # Gentle guidance should be added


def test_risk_ml_non_urgent_label_triggered(fake_pipe):
    # Set scores to trigger a non-urgent label (e.g., self_care)
    fake_pipe.run(urgent_care=0.1, see_doctor=0.1, self_care=0.8, info_only=0.1)
    state = {"user_query": "I have a minor issue", "messages": []}
    out = risk_ml.run(state)
    assert "alerts" not in out or not any("ML risk" in a for a in out.get("alerts", []))
    assert "messages" in out
    assert len(out["messages"]) == 1
    assert "Likely self-care with monitoring." in out["messages"][0]["content"]


def test_risk_ml_no_gentle_guidance_if_triggered(fake_pipe):
    # Set scores to trigger an alert, so no gentle guidance is added
    fake_pipe.run(urgent_care=0.8, see_doctor=0.1, self_care=0.1, info_only=0.1)
    state = {"user_query": "Urgent issue", "messages": []}
    out = risk_ml.run(state)
    assert any("ML risk: urgent_care" in a for a in out.get("alerts", []))
    assert "messages" not in out or not any(
        "gentle guidance" in m.get("content", "") for m in out.get("messages", [])
    )


def test_risk_ml_no_gentle_guidance_if_messages_present(fake_pipe):
    # Set scores below threshold, but messages already present
    fake_pipe.run(urgent_care=0.1, see_doctor=0.1, self_care=0.1, info_only=0.1)
    state = {
        "user_query": "Some query",
        "messages": [{"role": "assistant", "content": "Existing message"}],
    }
    out = risk_ml.run(state)
    assert "messages" in out
    assert len(out["messages"]) == 1  # Only existing message
    assert "Existing message" in out["messages"][0]["content"]
    assert "gentle guidance" not in out["messages"][0]["content"]


def test_risk_ml_no_gentle_guidance_if_no_pairs(monkeypatch):
    # Mock pipe to return no pairs
    mock_pipe = MagicMock()
    mock_pipe.return_value = {"labels": [], "scores": []}
    monkeypatch.setattr(risk_ml, "_get_pipe", lambda: mock_pipe)
    state = {"user_query": "Some query", "messages": []}
    out = risk_ml.run(state)
    assert "messages" not in out or not out["messages"]
