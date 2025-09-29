from app.tools import med_facts


def setup_function() -> None:
    med_facts.clear_cache()


def test_onset_for_canonical_en():
    fact = med_facts.onset_for("acetaminophen", language="en")
    assert fact is not None
    assert "30" in fact["summary"]
    assert fact["source_url"].startswith("https://")


def test_onset_for_alias_hebrew_language():
    fact = med_facts.onset_for("אקמול", language="he")
    assert fact is not None
    assert "אקמול" in fact["summary"]
    assert fact["source_label"]


def test_onset_for_falls_back_to_default_language():
    fact = med_facts.onset_for("ibuprofen", language="fr")
    assert fact is not None
    assert "Ibuprofen" in fact["summary"]


def test_onset_for_unknown_returns_none():
    assert med_facts.onset_for("unknown-med") is None
