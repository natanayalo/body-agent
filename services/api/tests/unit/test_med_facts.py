import json

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


def test_onset_for_missing_file(monkeypatch):
    med_facts.clear_cache()

    def fake_resolve() -> str:
        return "/nonexistent/path/med_facts.json"

    monkeypatch.setattr(med_facts, "_resolve_path", fake_resolve)
    assert med_facts.onset_for("acetaminophen") is None


def test_onset_for_missing_display_names(monkeypatch, tmp_path):
    med_facts.clear_cache()
    path = tmp_path / "med_facts.json"
    path.write_text(
        json.dumps(
            {
                "testmed": {
                    "name": "TestMed",
                    "aliases": [],
                    "onset": {"en": {"summary": "Works soon."}},
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(med_facts, "_resolve_path", lambda: str(path))
    fact = med_facts.onset_for("testmed", language="he")
    assert fact is not None
    assert fact["display_name"] == "TestMed"
    assert fact["summary"] == "Works soon."


def test_onset_for_missing_source(monkeypatch, tmp_path):
    med_facts.clear_cache()
    path = tmp_path / "med_facts.json"
    path.write_text(
        json.dumps(
            {
                "testmed": {
                    "name": "TestMed",
                    "aliases": ["alias"],
                    "onset": {"en": {"summary": "Works soon.", "follow_up": "Check."}},
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(med_facts, "_resolve_path", lambda: str(path))
    fact = med_facts.onset_for("alias", language="en")
    assert fact is not None
    assert fact["source_label"] == ""
    assert fact["source_url"] == ""


def test_onset_for_requires_summary(monkeypatch, tmp_path):
    med_facts.clear_cache()
    path = tmp_path / "med_facts.json"
    path.write_text(
        json.dumps(
            {
                "empty": {
                    "name": "Empty",
                    "aliases": [],
                    "onset": {"en": {}},
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(med_facts, "_resolve_path", lambda: str(path))
    assert med_facts.onset_for("empty") is None
