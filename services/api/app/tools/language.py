"""Lightweight language detection helpers."""

from __future__ import annotations

import re


SUPPORTED_LANGS = {"en", "he"}
LANG_ALIASES = {"iw": "he"}
DEFAULT_LANGUAGE = "en"

_HEBREW_CHARS = re.compile(r"[\u0590-\u05FF]")


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
    return True


def detect_language(text: str) -> str:
    return "he" if _likely_hebrew(text) else DEFAULT_LANGUAGE


def resolve_language(override: str | None, text: str) -> str:
    return normalize_language_code(override) or detect_language(text)
