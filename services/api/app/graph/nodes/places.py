from __future__ import annotations

import logging
import math
import re
from typing import Any, Dict, List, Tuple

from app.graph.state import BodyState
from app.tools.geo_tools import search_providers
from app.tools.es_client import get_es_client

logger = logging.getLogger(__name__)

# Dummy location for demo (Tel Aviv center). Replace with user-permitted geolocation
TLV = (32.0853, 34.7818)

WINDOW_RANGES = {
    "morning": range(5, 12),
    "afternoon": range(12, 17),
    "evening": range(17, 22),
}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def _hours_windows(hours: str) -> set[str]:
    if not hours:
        return set()
    matches = re.findall(r"(\d{1,2}):(\d{2})", hours)
    if len(matches) < 2:
        lower = hours.lower()
        return {window for window in WINDOW_RANGES if window in lower}

    start_hour = int(matches[0][0]) % 24
    end_hour = int(matches[-1][0]) % 24
    span: List[int]
    if end_hour > start_hour:
        span = list(range(start_hour, end_hour))
    else:
        span = list(range(start_hour, end_hour + 24)) or [start_hour]

    buckets: set[str] = set()
    for window, hour_range in WINDOW_RANGES.items():
        if any((h % 24) in hour_range for h in span):
            buckets.add(window)
    return buckets


def _normalize(values: List[float]) -> List[float]:
    if not values:
        return []
    v_max = max(values)
    if math.isclose(v_max, 0.0):
        return [0.0 for _ in values]
    return [v / v_max for v in values]


def _compute_candidate_meta(
    candidate: Dict[str, Any],
    semantic_norm: float,
    prefs: Dict[str, Any],
) -> Tuple[float, List[str], float | None]:
    reasons: List[str] = []
    distance_norm = 0.5
    distance_km: float | None = None

    geo = candidate.get("geo") or {}
    lat, lon = geo.get("lat"), geo.get("lon")
    if lat is not None and lon is not None:
        distance_km = _haversine_km(TLV[0], TLV[1], float(lat), float(lon))
        max_radius = prefs.get("max_distance_km") or 10.0
        if not isinstance(max_radius, (int, float)) or max_radius <= 0:
            max_radius = 10.0
        distance_norm = max(0.0, 1.0 - min(distance_km, max_radius) / max_radius)
        reasons.append(f"~{distance_km:.1f} km away")

    hours_fit = 0.5
    pref_window = prefs.get("hours_window")
    windows = _hours_windows(candidate.get("hours", "") or "")
    if pref_window:
        if windows and pref_window in windows:
            hours_fit = 1.0
            reasons.append(f"Open during {pref_window}")
        else:
            hours_fit = 0.0

    preferred_kinds = {k.lower() for k in prefs.get("preferred_kinds", [])}
    kind = (candidate.get("kind") or "").lower()
    if preferred_kinds and kind in preferred_kinds:
        semantic_norm = min(1.0, semantic_norm + 0.1)
        reasons.append(f"Matches preferred kind ({kind})")

    score = 0.6 * semantic_norm + 0.25 * distance_norm + 0.15 * hours_fit
    return score, reasons, distance_km


def run(state: BodyState, es_client=None) -> BodyState:
    es = es_client if es_client else get_es_client()
    q = state.get("user_query_redacted", state.get("user_query", ""))
    logger.debug(f"Searching providers for query: {q}")
    raw = search_providers(es, q, lat=TLV[0], lon=TLV[1], radius_km=10)
    logger.debug(f"Raw provider search results: {raw}")
    # dedupe by (name, phone) keeping highest score
    best: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for c in raw:
        name = c.get("name")
        phone = c.get("phone")
        if not name or not phone:
            continue
        key = (name, phone)
        if key not in best or c.get("_score", 0) > best[key].get("_score", 0):
            best[key] = c

    candidates = list(best.values())
    prefs: Dict[str, Any] = dict(state.get("preferences") or {})
    semantic_scores = [c.get("_score", 0.0) for c in candidates]
    semantic_norms = _normalize(semantic_scores)
    if not semantic_norms:
        semantic_norms = [1.0 for _ in candidates]

    ranked: list[Dict[str, Any]] = []
    for candidate, sem_norm in zip(candidates, semantic_norms):
        score, reasons, distance_km = _compute_candidate_meta(
            candidate, sem_norm, prefs
        )
        cand_with_meta = candidate.copy()
        cand_with_meta["score"] = round(score, 4)
        if distance_km is not None:
            cand_with_meta["distance_km"] = round(distance_km, 2)
        cand_with_meta["reasons"] = reasons
        ranked.append(cand_with_meta)

    ranked.sort(key=lambda c: c.get("score", 0.0), reverse=True)
    state["candidates"] = ranked
    logger.debug(f"Final candidates after scoring: {state['candidates']}")
    return state
