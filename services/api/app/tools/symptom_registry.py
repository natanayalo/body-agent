"""Symptom registry helpers for query expansion and doc routing."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from app.config import settings

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None

logger = logging.getLogger(__name__)

_CACHE: Dict[str, dict] = {}
_CACHE_MTIME: float | None = None


def _registry_path() -> Path:
    env_path = getattr(settings, "symptom_registry_path", None)
    if env_path:
        return Path(env_path)
    return Path(__file__).resolve().parent.parent / "registry" / "symptoms.yml"


def _load_registry() -> Dict[str, dict]:
    global _CACHE, _CACHE_MTIME

    path = _registry_path()
    try:
        mtime = path.stat().st_mtime
    except FileNotFoundError:
        logger.debug("Symptom registry not found at %s", path)
        _CACHE = {}
        _CACHE_MTIME = None
        return _CACHE

    if _CACHE_MTIME == mtime:
        return _CACHE

    if yaml is None:
        logger.warning(
            "PyYAML not installed; symptom registry disabled (missing %s)", path
        )
        _CACHE = {}
        _CACHE_MTIME = mtime
        return _CACHE

    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}

    if not isinstance(data, dict):
        logger.warning("Expected symptom registry mapping, got %s", type(data).__name__)
        data = {}

    _CACHE = data
    _CACHE_MTIME = mtime
    return _CACHE


def get_registry() -> Dict[str, dict]:
    """Return the symptom registry mapping (cached)."""

    return _load_registry()


def match_query(text: str) -> List[Tuple[str, dict]]:
    """Return registry entries whose phrases appear in *text*."""

    registry = get_registry()
    if not registry or not text:
        return []

    text_norm = text.lower()
    matches: List[Tuple[str, dict]] = []

    for key, entry in registry.items():
        phrases = entry.get("phrases", {})
        if not isinstance(phrases, dict):
            continue

        found = False
        for lang_terms in phrases.values():
            if not isinstance(lang_terms, (list, tuple)):
                continue
            for raw_term in lang_terms:
                term = (raw_term or "").strip().lower()
                if not term:
                    continue
                if term in text_norm:
                    found = True
                    break
            if found:
                break
        if found:
            matches.append((key, entry))

    return matches


def expansion_terms(
    matches: Iterable[Tuple[str, dict]], preferred_language: str
) -> List[str]:
    """Collect deduped expansion terms for the matched registry entries."""

    seen = set()
    expansions: List[str] = []
    pref = (preferred_language or "").lower()

    for _key, entry in matches:
        phrases = entry.get("phrases", {})
        if not isinstance(phrases, dict):
            continue

        # Always prioritise English synonyms to improve cross-language recall
        for term in _iter_terms(phrases.get("en")):
            lowered = term.lower()
            if lowered not in seen:
                seen.add(lowered)
                expansions.append(term)

        # Add other language variants except the preferred language
        for lang, lang_terms in phrases.items():
            if lang.lower() == "en" or lang.lower() == pref:
                continue
            for term in _iter_terms(lang_terms):
                lowered = term.lower()
                if lowered not in seen:
                    seen.add(lowered)
                    expansions.append(term)

        # Finally, include additional variants in the preferred language that differ from the text
        for term in _iter_terms(phrases.get(pref)):
            lowered = term.lower()
            if lowered not in seen:
                seen.add(lowered)
                expansions.append(term)

    return expansions


def doc_refs(matches: Iterable[Tuple[str, dict]]) -> List[dict]:
    """Return document references declared for the matched entries."""

    refs: List[dict] = []
    seen: set[str] = set()
    for _key, entry in matches:
        docs = entry.get("docs", [])
        if not isinstance(docs, list):
            continue
        for ref in docs:
            if not isinstance(ref, dict):
                continue
            key = json.dumps(ref, sort_keys=True, ensure_ascii=False)
            if key in seen:
                continue
            seen.add(key)
            refs.append(ref)
    return refs


def _iter_terms(raw_terms) -> Iterable[str]:
    if not isinstance(raw_terms, (list, tuple)):
        return []
    return [t for t in raw_terms if isinstance(t, str) and t.strip()]
