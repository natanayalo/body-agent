"""Medication normalization helpers for brand and multilingual aliases."""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from app.tools.language import normalize_language_code

_HEBREW_DOSAGE_UNITS = ("מ" "ג", "גרם")  # rendered as מ"ג (mg)

# Base lexicon: canonical ingredient -> set of aliases (lowercase, stripped)
_LEXICON: Dict[str, List[str]] = {
    "acetaminophen": [
        "acetaminophen",
        "paracetamol",
        "tylenol",
        "panadol",
        "aca mol",
        "acamol",
        "אקמול",
        "אדקס",
        "דקסמול",
    ],
    "ibuprofen": [
        "ibuprofen",
        "advil",
        "motrin",
        "nurofen",
        "נורופן",
        "איבופרופן",
    ],
    "aspirin": [
        "aspirin",
        "אספירין",
        "cartia",
        "ecotrin",
    ],
    "naproxen": [
        "naproxen",
        "aleve",
        "naproxen sodium",
        "נקסין",
        "נרקסן",
    ],
}

_ALIAS_TO_CANONICAL: Dict[str, str] = {}
for canonical, aliases in _LEXICON.items():
    for alias in aliases:
        _ALIAS_TO_CANONICAL[alias.lower()] = canonical

_ALIASES_BY_LENGTH: List[str] = sorted(
    _ALIAS_TO_CANONICAL.keys(), key=len, reverse=True
)


def _strip_dosage(value: str) -> str:
    cleaned = re.sub(r"\b\d+(\.\d+)?\s?(mg|mcg|ml|g)\b", "", value, flags=re.IGNORECASE)
    for unit in _HEBREW_DOSAGE_UNITS:
        cleaned = cleaned.replace(unit, "")
    return cleaned


def _normalize_token(value: str) -> str:
    value = _strip_dosage(value)
    value = re.sub(
        r"[^\w\s\u0590-\u05FF]", " ", value
    )  # retain letters + numbers + Hebrew
    value = re.sub(r"\s+", " ", value)
    return value.strip().lower()


def normalize_medication_name(name: str) -> Optional[Dict[str, str]]:
    """Return canonical ingredient for a medication name.

    Falls back to a cleaned token so downstream code retains current behaviour
    even when the alias is unknown.
    """

    if not name:
        return None
    cleaned = _normalize_token(name)
    if not cleaned:
        return None

    canonical = _ALIAS_TO_CANONICAL.get(cleaned)
    if canonical:
        return {"ingredient": canonical, "alias": cleaned}

    # Fall back to the longest matching alias contained in the cleaned string.
    for alias in _ALIASES_BY_LENGTH:
        if alias in cleaned and len(alias) > 2:
            return {"ingredient": _ALIAS_TO_CANONICAL[alias], "alias": alias}

    return {"ingredient": cleaned}


def normalize_fact(fact: Dict[str, object]) -> None:
    if fact.get("entity") != "medication":
        return
    name = str(fact.get("name", ""))
    normalized = normalize_medication_name(name)
    if not normalized:
        return
    existing = fact.get("normalized")
    if isinstance(existing, dict):
        slot = dict(existing)
    else:
        slot = {}
    slot["ingredient"] = normalized["ingredient"]
    fact["normalized"] = slot


def find_medications_in_text(text: str, language: Optional[str] = None) -> List[str]:
    if not text:
        return []

    checked = set()
    lowered = text.lower()
    lang = normalize_language_code(language)
    for alias, canonical in _ALIAS_TO_CANONICAL.items():
        if lang == "he":
            pattern = re.compile(
                rf"(?<![\w\u0590-\u05FF])(?:ו)?{re.escape(alias)}(?![\w\u0590-\u05FF])"
            )
        else:
            pattern = re.compile(
                rf"(?<![\w\u0590-\u05FF]){re.escape(alias)}(?![\w\u0590-\u05FF])"
            )
        if pattern.search(lowered):
            checked.add(canonical)
    return sorted(checked)
