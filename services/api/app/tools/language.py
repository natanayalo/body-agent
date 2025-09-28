"""Lightweight language detection helpers."""

from __future__ import annotations

import re


SUPPORTED_LANGS = {"en", "he"}
LANG_ALIASES = {"iw": "he"}
DEFAULT_LANGUAGE = "en"

_HEBREW_CHARS = re.compile(r"[\u0590-\u05FF]")


def _compile_hebrew_phrase(phrase: str) -> re.Pattern[str]:
    escaped = re.escape(phrase)
    return re.compile(rf"(?<!\S){escaped}(?!\S)")


_HE_TO_EN_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (_compile_hebrew_phrase("כאבי בטן"), "stomach pain"),
    (_compile_hebrew_phrase("כאב בטן"), "stomach pain"),
    (_compile_hebrew_phrase("כאב ראש"), "headache"),
    (_compile_hebrew_phrase("אקמול"), "acetaminophen"),
    (_compile_hebrew_phrase("נורופן"), "ibuprofen"),
    (_compile_hebrew_phrase("מתי זה אמור להשפיע"), "when will it start working"),
    (_compile_hebrew_phrase("מתי זה מתחיל להשפיע"), "when does it start working"),
    (_compile_hebrew_phrase("מתי זה משפיע"), "when does it start working"),
    (_compile_hebrew_phrase("כמה זמן"), "how long"),
    (_compile_hebrew_phrase("תופעות לוואי"), "side effects"),
    (_compile_hebrew_phrase("חום"), "fever"),
)


def normalize_language_code(lang: str | None) -> str | None:
    if not lang:
        return None
    code = lang.lower().strip()
    mapped = LANG_ALIASES.get(code, code)
    return mapped if mapped in SUPPORTED_LANGS else None


def _likely_hebrew(text: str) -> bool:
    if not text:
        return False
    matches = _HEBREW_CHARS.findall(text)
    if not matches:
        return False
    # Treat as Hebrew if at least 20% of letters are Hebrew or >=3 chars
    hebrew_count = len(matches)
    letter_count = sum(ch.isalpha() for ch in text)
    if hebrew_count >= 3:
        return True
    if letter_count:
        return hebrew_count / letter_count >= 0.2
    return True  # pragma: no cover (fallback for all-non-letter strings)


def detect_language(text: str) -> str:
    return "he" if _likely_hebrew(text) else DEFAULT_LANGUAGE


def resolve_language(override: str | None, text: str) -> str:
    return normalize_language_code(override) or detect_language(text)


def pivot_to_english(text: str, language: str | None) -> str | None:
    """Best-effort HE→EN pivot for retrieval.

    Returns lowercase English text when we can confidently replace common phrases.
    Falls back to ``None`` when we cannot derive a useful pivot.
    """

    if not text:
        return None

    lang = normalize_language_code(language)
    if lang is None:
        if language:
            cleaned = _strip_extra_whitespace(text)
            return cleaned.lower() if cleaned else None
        return None

    if lang == "en":
        return None

    if not _HEBREW_CHARS.search(text):
        return None

    lowered = text.lower()
    pivot = lowered
    replaced = False
    for pattern, replacement in _HE_TO_EN_REPLACEMENTS:
        new_value = pattern.sub(replacement, pivot)
        if new_value != pivot:
            replaced = True
        pivot = new_value

    cleaned = _strip_extra_whitespace(_HEBREW_CHARS.sub("", pivot))
    if cleaned:
        return cleaned

    return (
        pivot if replaced else None
    )  # pragma: no cover (no mixed-script fallback yet)


def _strip_extra_whitespace(value: str) -> str:
    value = re.sub(r"\s+", " ", value)
    return value.strip()
