"""Deterministic medication fact lookup (onset windows, sources)."""

from __future__ import annotations

import json
import os
import logging
from functools import lru_cache
from typing import Dict, Optional, Tuple

from app.tools.language import DEFAULT_LANGUAGE

_DEFAULT_FACTS_PATH = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "..", "seeds", "med_facts.json"
    )
)


logger = logging.getLogger(__name__)


def _resolve_path() -> str:
    return os.getenv("MED_FACTS_PATH", _DEFAULT_FACTS_PATH)


@lru_cache(maxsize=1)
def _load_facts() -> Dict[str, dict]:
    path = _resolve_path()
    try:
        with open(path, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed loading med facts from %s: %s", path, exc)
        return {}

    facts: Dict[str, dict] = {}
    for key, value in raw.items():
        if not isinstance(value, dict):
            continue
        canonical = key.lower().strip()
        facts[canonical] = value
    return facts


@lru_cache(maxsize=1)
def _alias_map() -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for canonical, payload in _load_facts().items():
        mapping[canonical] = canonical
        aliases = payload.get("aliases", [])
        if isinstance(aliases, list):
            for alias in aliases:
                if isinstance(alias, str) and alias.strip():
                    mapping[alias.strip().lower()] = canonical
    return mapping


def _localize(entry: dict, language: Optional[str]) -> Tuple[str, str, str]:
    lang = language if language and language in (entry.get("onset") or {}) else None
    onset_map = entry.get("onset") or {}
    localized = onset_map.get(lang) if lang else None
    if not isinstance(localized, dict):
        localized = onset_map.get(DEFAULT_LANGUAGE, {})
    summary = ""
    follow_up = ""
    if isinstance(localized, dict):
        summary = str(localized.get("summary", "")).strip()
        follow_up = str(localized.get("follow_up", "")).strip()

    display = entry.get("display_names", {})
    display_name = ""
    if isinstance(display, dict):
        display_name = str(display.get(language or "", "")).strip()
        if not display_name:
            display_name = str(display.get(DEFAULT_LANGUAGE, "")).strip()
    if not display_name:
        display_name = str(entry.get("name", "")).strip() or ""
    return display_name, summary, follow_up


def onset_for(ingredient: str, language: Optional[str] = None) -> Optional[dict]:
    if not ingredient:
        return None
    key = ingredient.strip().lower()
    canonical = _alias_map().get(key)
    if not canonical:
        return None
    entry = _load_facts().get(canonical)
    if not entry:
        return None

    display_name, summary, follow_up = _localize(entry, language)
    if not summary:
        return None

    source = entry.get("source", {})
    source_label = str(source.get("label", "")).strip()
    source_url = str(source.get("url", "")).strip()

    return {
        "ingredient": canonical,
        "display_name": display_name or canonical,
        "summary": summary,
        "follow_up": follow_up,
        "source_label": source_label,
        "source_url": source_url,
    }


def clear_cache() -> None:
    """Helper for tests to reset cached facts."""

    _load_facts.cache_clear()
    _alias_map.cache_clear()
