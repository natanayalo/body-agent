from app.tools.language import (
    DEFAULT_LANGUAGE,
    detect_language,
    normalize_language_code,
    resolve_language,
    pivot_to_english,
)


def test_normalize_language_code_aliases():
    assert normalize_language_code("iw") == "he"
    assert normalize_language_code("HE") == "he"
    assert normalize_language_code("EN") == "en"
    assert normalize_language_code("fr") is None


def test_detect_language_handles_hebrew_text():
    sample = "יש לי חום גבוה ומעט כאב ראש כבר יומיים"
    assert detect_language(sample) == "he"


def test_resolve_language_prefers_override():
    assert resolve_language("en", "טקסט בעברית") == "en"
    assert resolve_language(None, "טקסט בעברית") == "he"
    assert resolve_language(None, "plain english text") == DEFAULT_LANGUAGE


def test_detect_language_threshold_proportion():
    # Two Hebrew letters among ~10 alphabetic chars (~20%) should classify as Hebrew
    sample = "abבגcdefgh"
    assert detect_language(sample) == "he"


def test_pivot_to_english_maps_common_phrases():
    assert pivot_to_english("יש לי כאבי בטן", "he") == "stomach pain"


def test_pivot_to_english_returns_none_for_en():
    assert pivot_to_english("I have a fever", "en") is None


def test_detect_language_empty_defaults_to_en():
    assert detect_language("") == DEFAULT_LANGUAGE


def test_pivot_to_english_other_locale_returns_lower():
    assert pivot_to_english("Dolor de estómago", "es") == "dolor de estómago"


def test_pivot_to_english_empty_text():
    assert pivot_to_english("", "he") is None


def test_pivot_to_english_he_language_without_hebrew():
    assert pivot_to_english("Call clinic", "he") is None


def test_pivot_to_english_without_language_override():
    assert pivot_to_english("Some text", None) is None


def test_pivot_to_english_does_not_replace_substrings():
    # "חומר" contains the letters of "חום" but should not trigger replacement
    assert "acetaminophen" not in (pivot_to_english("לחומר יש טעם", "he") or "")
