from app.tools.language import (
    DEFAULT_LANGUAGE,
    detect_language,
    normalize_language_code,
    resolve_language,
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
