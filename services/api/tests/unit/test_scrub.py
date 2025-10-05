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


def test_scrub_redacts_government_ids():
    query = "My passport number AB123456 is expired and ID 987654321 needs renewal"
    state: BodyState = {"user_query": query}
    out = scrub.run(state)
    redacted = out["user_query_redacted"].lower()
    assert "[gov_id]" in redacted
    assert "ab123456" not in redacted
    assert "987654321" not in redacted


def test_scrub_redacts_hebrew_id_and_address():
    query = "תעודת זהות 123456789 ברחוב אבן גבירול 15 תל אביב"
    state: BodyState = {"user_query": query}
    out = scrub.run(state)
    redacted = out["user_query_redacted"]
    assert "[gov_id]" in redacted
    assert "[address]" in redacted
    assert "123456789" not in redacted
    assert "אבן גבירול 15" not in redacted


def test_scrub_redacts_address_fragments():
    query = "Send the package to 742 Evergreen Terrace tomorrow"
    state: BodyState = {"user_query": query}
    out = scrub.run(state)
    redacted = out["user_query_redacted"].lower()
    assert "[address]" in redacted
    assert "742" not in redacted
    assert "evergreen terrace" not in redacted


def test_scrub_redacts_long_english_street():
    query = "Mail it to 1200 Martin Luther King Jr Boulevard tonight"
    state: BodyState = {"user_query": query}
    out = scrub.run(state)
    redacted = out["user_query_redacted"].lower()
    assert "[address]" in redacted
    assert "1200" not in redacted
    assert "martin luther king jr boulevard" not in redacted
