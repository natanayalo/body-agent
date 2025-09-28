from app.tools import med_normalize


def test_normalize_medication_name_hebrew_brand():
    result = med_normalize.normalize_medication_name("אקמול 500 מ" "ג")
    assert result is not None
    assert result["ingredient"] == "acetaminophen"


def test_normalize_medication_name_english_brand():
    result = med_normalize.normalize_medication_name("Nurofen 200mg")
    assert result is not None
    assert result["ingredient"] == "ibuprofen"


def test_find_medications_in_text_multilingual():
    meds = med_normalize.find_medications_in_text("נטלתי אקמול ונורופן", language="he")
    assert meds == ["acetaminophen", "ibuprofen"]


def test_find_medications_in_text_hebrew_prefix_only_for_he():
    meds_he = med_normalize.find_medications_in_text("ונורופן", language="he")
    assert meds_he == ["ibuprofen"]
    meds_en = med_normalize.find_medications_in_text("ונורופן", language="en")
    assert meds_en == []


def test_find_medications_in_text_ignores_substrings():
    meds = med_normalize.find_medications_in_text("החומרים", language="he")
    assert meds == []


def test_normalize_medication_name_empty_returns_none():
    assert med_normalize.normalize_medication_name("") is None


def test_find_medications_in_text_empty_returns_empty_list():
    assert med_normalize.find_medications_in_text("", language="he") == []


def test_normalize_medication_name_prefers_longest_alias(monkeypatch):
    # Inject a short alias to ensure the longer match wins.
    monkeypatch.setitem(med_normalize._ALIAS_TO_CANONICAL, "אק", "acetaminophen")
    monkeypatch.setattr(
        med_normalize,
        "_ALIASES_BY_LENGTH",
        sorted(med_normalize._ALIAS_TO_CANONICAL.keys(), key=len, reverse=True),
    )

    result = med_normalize.normalize_medication_name("אקמול")
    assert result is not None
    assert result["ingredient"] == "acetaminophen"
    assert result["alias"] == "אקמול"
