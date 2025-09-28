import importlib

from app.tools import symptom_registry


def test_symptom_registry_expansions_and_refs():
    importlib.reload(symptom_registry)

    matches = symptom_registry.match_query("כאבי בטן חזקים")
    assert matches, "Expected stomach pain registry match"

    expansions = symptom_registry.expansion_terms(matches, "he")
    lowered = [term.lower() for term in expansions]
    assert "abdominal pain" in lowered
    assert "stomach pain" in lowered

    refs = symptom_registry.doc_refs(matches)
    assert any(ref.get("title") == "Abdominal Pain Home Care" for ref in refs)


def test_symptom_registry_handles_missing_and_invalid_files(monkeypatch, tmp_path):
    importlib.reload(symptom_registry)

    missing_path = tmp_path / "missing.yml"
    monkeypatch.setattr(
        symptom_registry.settings, "symptom_registry_path", str(missing_path)
    )
    importlib.reload(symptom_registry)
    assert symptom_registry.get_registry() == {}

    bad_path = tmp_path / "bad.yml"
    bad_path.write_text("- 1\n- 2\n", encoding="utf-8")
    monkeypatch.setattr(
        symptom_registry.settings, "symptom_registry_path", str(bad_path)
    )
    importlib.reload(symptom_registry)
    assert symptom_registry.get_registry() == {}

    importlib.reload(symptom_registry)


def test_symptom_registry_yaml_optional(monkeypatch, tmp_path):
    valid_path = tmp_path / "symptoms.yml"
    valid_path.write_text(
        "stomach: {phrases: {en: [stomach pain]}}\n", encoding="utf-8"
    )
    monkeypatch.setattr(
        symptom_registry.settings, "symptom_registry_path", str(valid_path)
    )
    importlib.reload(symptom_registry)
    monkeypatch.setattr(symptom_registry, "yaml", None, raising=False)
    # reset cache to force reload with yaml missing
    symptom_registry._CACHE = {}
    assert symptom_registry.get_registry() == {}

    importlib.reload(symptom_registry)


def test_symptom_registry_expansion_dedup_and_fallback(monkeypatch):
    importlib.reload(symptom_registry)

    matches = [
        ("ignore", {"phrases": "not-a-dict"}),
        (
            "dup",
            {
                "phrases": {
                    "en": ["Pain", "pain", ""],
                    "es": ["dolor", "Dolor"],
                    "he": [""],
                }
            },
        ),
        ("empty", {"phrases": {"de": [""]}}),
    ]

    expansions = symptom_registry.expansion_terms(matches, "en")
    assert expansions == ["Pain", "dolor"]

    # Ensure fallback path is used when env var is blank
    monkeypatch.setattr(symptom_registry.settings, "symptom_registry_path", "")
    path = symptom_registry._registry_path()
    assert path.name == "symptoms.yml"

    importlib.reload(symptom_registry)


def test_symptom_registry_match_skips_non_list_variants(monkeypatch):
    importlib.reload(symptom_registry)

    registry = {
        "mix": {"phrases": {"en": ["pain"], "he": "טקסט"}},
    }

    monkeypatch.setattr(symptom_registry, "get_registry", lambda: registry)
    matches = symptom_registry.match_query("Pain in arm")
    assert matches == [("mix", registry["mix"])]

    importlib.reload(symptom_registry)


def test_symptom_registry_non_list_variant_without_match(monkeypatch):
    importlib.reload(symptom_registry)

    registry = {"mix": {"phrases": {"en": ["pain"], "he": "טקסט"}}}
    monkeypatch.setattr(symptom_registry, "get_registry", lambda: registry)

    matches = symptom_registry.match_query("no related symptom")
    assert matches == []

    importlib.reload(symptom_registry)

    registry = {
        "bad": {"phrases": "oops", "docs": "skip-me"},
        "ok": {
            "phrases": {"en": ["", "match me"], "he": "ignored"},
            "docs": [{"title": "DocA"}, "not-a-dict", {"title": "DocA"}],
        },
    }

    monkeypatch.setattr(symptom_registry, "get_registry", lambda: registry)

    matches = symptom_registry.match_query("Match me please")
    assert matches == [("ok", registry["ok"])]

    refs = symptom_registry.doc_refs([("bad", registry["bad"]), *matches])
    assert refs == [{"title": "DocA"}]

    expansions = symptom_registry.expansion_terms(matches, "en")
    assert expansions == ["match me"]

    importlib.reload(symptom_registry)
