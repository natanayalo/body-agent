import os
import json
import pytest
from app.graph.nodes import supervisor
from app.graph.state import BodyState


@pytest.fixture(autouse=True)
def reload_supervisor_module():
    import importlib

    importlib.reload(supervisor)
    yield


def test_load_exemplars_from_file_success(monkeypatch, tmp_path):
    mapping = {
        "symptom": ["test symptom"],
        "meds": ["test meds"],
        "appointment": ["test appointment"],
        "routine": ["test routine"],
        "unknown": ["drop"],
    }
    file_path = tmp_path / "exemplars.json"
    file_path.write_text(json.dumps(mapping), encoding="utf-8")

    monkeypatch.setenv("INTENT_EXEMPLARS_PATH", str(file_path))

    import importlib

    importlib.reload(supervisor)

    assert supervisor._EXEMPLARS["symptom"] == ["test symptom"]
    assert "unknown" not in supervisor._EXEMPLARS


def test_load_exemplars_from_file_malformed(monkeypatch, tmp_path):
    file_path = tmp_path / "malformed.json"
    file_path.write_text("{not valid json}", encoding="utf-8")
    monkeypatch.setenv("INTENT_EXEMPLARS_PATH", str(file_path))

    import importlib

    importlib.reload(supervisor)

    assert supervisor._EXEMPLARS == supervisor._DEFAULT_EXAMPLES


def test_load_exemplars_from_file_non_existent(monkeypatch):
    monkeypatch.setenv("INTENT_EXEMPLARS_PATH", "/tmp/non_existent_exemplars.json")

    import importlib

    importlib.reload(supervisor)

    assert supervisor._EXEMPLARS == supervisor._DEFAULT_EXAMPLES


def test_detect_intent_returns_other_if_no_match(fake_embed):
    # Set up fake_embed to return all zeros for all inputs
    # This will make all scores 0.0
    fake_embed.return_value = [0.0, 0.0, 0.0]

    # Temporarily set thresholds to ensure no match
    original_threshold = supervisor._THRESHOLD
    original_margin = supervisor._MARGIN
    supervisor._THRESHOLD = 1.0  # High threshold
    supervisor._MARGIN = 1.0  # High margin

    intent = supervisor.detect_intent("This is a completely unrelated query")
    assert intent == "other"

    # Restore original thresholds
    supervisor._THRESHOLD = original_threshold
    supervisor._MARGIN = original_margin


def test_load_exemplars_from_file_empty_or_invalid_content(monkeypatch, tmp_path):
    file_path = tmp_path / "invalid.json"
    file_path.write_text(json.dumps({"unknown_key": ["some_value"]}), encoding="utf-8")
    monkeypatch.setenv("INTENT_EXEMPLARS_PATH", str(file_path))

    import importlib

    importlib.reload(supervisor)

    assert supervisor._EXEMPLARS == supervisor._DEFAULT_EXAMPLES


def test_detect_intent_with_no_exemplars(monkeypatch):
    monkeypatch.setattr(supervisor, "_EX_VECS", {})
    intent = supervisor.detect_intent("any query")
    assert intent == "other"


def test_detect_intent_with_unknown_intent_in_exemplars(monkeypatch, fake_embed):
    # This is a tricky case to test since _load_exemplars filters unknown intents.
    # We bypass it by directly mocking _EX_VECS.
    import numpy as np

    # Mock _EX_VECS to include an unknown intent with a high-scoring vector
    mock_vecs = {
        "symptom": np.array([[0.1, 0.1, 0.1]]),
        "unknown_intent": np.array([[0.9, 0.9, 0.9]]),
    }
    monkeypatch.setattr(supervisor, "_EX_VECS", mock_vecs)

    # Make the fake_embed return a vector that is very close to the unknown_intent vector
    fake_embed.return_value = [0.9, 0.9, 0.9]

    # Ensure thresholds are met
    monkeypatch.setattr(supervisor, "_THRESHOLD", 0.5)
    monkeypatch.setattr(supervisor, "_MARGIN", 0.1)

    intent = supervisor.detect_intent("query for unknown")
    assert intent == "other"


def test_detect_intent_hebrew_restaurant(monkeypatch, fake_embed):
    intent = supervisor.detect_intent("איפה אפשר לאכול לידי?")
    assert intent == "other"


def test_detect_intent_hebrew_stomach_pain(monkeypatch):
    intent = supervisor.detect_intent("מה אפשר לקחת כדי להקל על כאבי בטן?")
    assert intent == "symptom"


def test_run_records_normalized_query_meds(monkeypatch):
    state = BodyState(
        user_query="אקמול ונורופן",
        user_query_redacted="אקמול ונורופן",
        language="he",
    )

    out = supervisor.run(state)
    meds = out.get("debug", {}).get("normalized_query_meds")
    assert meds == ["acetaminophen", "ibuprofen"]


def test_run_sets_sub_intent_onset():
    state = BodyState(
        user_query="When will ibuprofen start working?",
        user_query_redacted="When will ibuprofen start working?",
        language="en",
    )

    out = supervisor.run(state)
    assert out.get("sub_intent") == "onset"


def test_run_sets_sub_intent_interaction_hebrew():
    state = BodyState(
        user_query="אפשר לקחת אקמול עם נורופן?",
        user_query_redacted="אפשר לקחת אקמול עם נורופן?",
        language="he",
    )

    out = supervisor.run(state)
    assert out.get("sub_intent") == "interaction"


def test_run_sets_sub_intent_refill():
    state = BodyState(
        user_query="Reminder to refill my meds",
        user_query_redacted="Reminder to refill my meds",
        language="en",
    )

    out = supervisor.run(state)
    assert out.get("sub_intent") == "refill"


def test_run_sets_sub_intent_onset_hebrew_without_med_name():
    state = BodyState(
        user_query="מתי התרופה אמורה להשפיע?",
        user_query_redacted="מתי התרופה אמורה להשפיע?",
        language="he",
    )

    out = supervisor.run(state)
    assert out.get("intent") == "meds"
    assert out.get("sub_intent") == "onset"


def test_run_sets_sub_intent_onset_hebrew_short_phrase():
    state = BodyState(
        user_query="אקמול מתי משפיע?",
        user_query_redacted="אקמול מתי משפיע?",
        language="he",
    )

    out = supervisor.run(state)
    assert out.get("intent") == "meds"
    assert out.get("sub_intent") == "onset"


def test_run_sets_sub_intent_interaction_with_phrase():
    state = BodyState(
        user_query="Interaction with ibuprofen?",
        user_query_redacted="Interaction with ibuprofen?",
        language="en",
    )

    out = supervisor.run(state)
    assert out.get("intent") == "meds"
    assert out.get("sub_intent") == "interaction"


def test_run_schedule_requires_med_context():
    state = BodyState(
        user_query="Remind me tomorrow",
        user_query_redacted="Remind me tomorrow",
        language="en",
    )

    out = supervisor.run(state)
    assert out.get("intent") != "meds"
    assert "sub_intent" not in out


def test_run_sets_sub_intent_schedule_with_med_context():
    state = BodyState(
        user_query="Remind me to take my meds every morning",
        user_query_redacted="Remind me to take my meds every morning",
        language="en",
    )

    out = supervisor.run(state)
    assert out.get("intent") == "meds"
    assert out.get("sub_intent") == "schedule"


def test_run_sub_intent_none_when_no_keywords():
    import importlib

    importlib.reload(supervisor)

    state = BodyState(
        user_query="Checking my appointment schedule",
        user_query_redacted="Checking my appointment schedule",
        language="en",
    )

    out = supervisor.run(state)
    assert "sub_intent" not in out


def test_loads_jsonl_exemplars(monkeypatch, tmp_path):
    # Prepare a JSONL file with exemplars
    p = tmp_path / "exemplars.jsonl"
    lines = [
        {"intent": "symptom", "text": "I have a fever"},
        {"intent": "appointment", "text": "book a lab"},
        {"intent": "symptom", "text": "כאבי בטן"},
    ]
    p.write_text("\n".join(json.dumps(x) for x in lines), encoding="utf-8")

    monkeypatch.setenv("INTENT_EXEMPLARS_PATH", str(p))
    import importlib
    import app.graph.nodes.supervisor as sup

    importlib.reload(sup)

    # Should route stomach pain to symptom based on JSONL exemplars
    assert sup.detect_intent("מה אפשר לקחת כדי להקל על כאבי בטן?") == "symptom"


def test_watches_exemplars_for_changes(monkeypatch, tmp_path):
    # Start with JSON mapping that lacks appointment
    p = tmp_path / "exemplars.json"
    mapping = {"symptom": ["I have a fever"]}
    p.write_text(json.dumps(mapping), encoding="utf-8")

    monkeypatch.setenv("INTENT_EXEMPLARS_PATH", str(p))
    monkeypatch.setenv("INTENT_EXEMPLARS_WATCH", "true")

    import importlib
    import app.graph.nodes.supervisor as sup

    importlib.reload(sup)

    # With no appointment exemplars, a booking query should abstain to other
    assert sup.detect_intent("book a lab appointment") == "other"

    # Now add appointment exemplars and bump mtime by rewriting the file
    mapping["appointment"] = ["book a lab", "schedule a doctor visit"]
    prev_stat = os.stat(p)
    p.write_text(json.dumps(mapping), encoding="utf-8")
    os.utime(
        p,
        ns=(prev_stat.st_mtime_ns + 1_000_000, prev_stat.st_mtime_ns + 1_000_000),
    )

    # After change, watch should reload and improve routing
    out = sup.detect_intent("book a lab appointment")
    assert out == "appointment"

    # Switching PATH should trigger a reload to the new file
    second = tmp_path / "second.json"
    second.write_text(
        json.dumps({"appointment": ["book a follow-up appointment"]}),
        encoding="utf-8",
    )

    monkeypatch.setenv("INTENT_EXEMPLARS_PATH", str(second))

    assert sup.detect_intent("book a follow-up appointment") == "appointment"
