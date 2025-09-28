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


def test_find_medications_in_text_ignores_substrings():
    meds = med_normalize.find_medications_in_text("החומרים", language="he")
    assert meds == []


def test_normalize_medication_name_empty_returns_none():
    assert med_normalize.normalize_medication_name("") is None


def test_find_medications_in_text_empty_returns_empty_list():
    assert med_normalize.find_medications_in_text("", language="he") == []
