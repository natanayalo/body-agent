from app.graph.nodes import scrub
from app.graph.state import BodyState


def test_scrub_detects_language_from_query():
    state: BodyState = {"user_query": "יש לי כאב ראש"}
    out = scrub.run(state)
    assert out["language"] == "he"
    assert out["user_query_redacted"].startswith("יש")
    assert out["user_query_pivot"] == "headache"


def test_scrub_normalizes_existing_language_code():
    state: BodyState = {"user_query": "Call clinic", "language": "IW"}
    out = scrub.run(state)
    assert out["language"] == "he"
    assert out.get("user_query_pivot") is None


def test_scrub_keeps_english_without_pivot():
    state: BodyState = {"user_query": "I have stomach pain"}
    out = scrub.run(state)
    assert out["language"] == "en"
    assert "user_query_pivot" not in out
