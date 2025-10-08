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
DEFAULT_RADIUS_KM = 10.0

WINDOW_RANGES = {
    "morning": range(5, 12),
    "afternoon": range(12, 17),
    "evening": range(17, 24),
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
        span = list(range(start_hour, end_hour + 24))

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


def _should_replace_candidate(
    existing: Tuple[Dict[str, Any], float | None],
    candidate: Tuple[Dict[str, Any], float | None],
    travel_limit_km: float | None,
) -> bool:
    existing_candidate, existing_distance = existing
    new_candidate, new_distance = candidate

    if travel_limit_km is not None:
        existing_in_range = (
            existing_distance is not None and existing_distance <= travel_limit_km
        )
        new_in_range = new_distance is not None and new_distance <= travel_limit_km
        if existing_in_range != new_in_range:
            return new_in_range
        if new_in_range and existing_in_range:
            if (
                new_distance is not None
                and existing_distance is not None
                and new_distance < existing_distance - 1e-6
            ):
                return True
            if (
                new_distance is not None
                and existing_distance is not None
                and existing_distance < new_distance - 1e-6
            ):
                return False

    existing_score = float(existing_candidate.get("_score", 0.0))
    new_score = float(new_candidate.get("_score", 0.0))
    if not math.isclose(new_score, existing_score):
        return new_score > existing_score

    if (
        new_distance is not None
        and existing_distance is not None
        and new_distance < existing_distance - 1e-6
    ):
        return True

    return False


def _get_travel_limit(prefs: Dict[str, Any]) -> float | None:
    raw = prefs.get("max_travel_km") or prefs.get("max_distance_km")
    if raw is None:
        return None
    try:
        limit = float(raw)
    except (TypeError, ValueError):
        return None
    if limit <= 0:
        return None
    return limit


def _candidate_distance(candidate: Dict[str, Any]) -> float | None:
    geo = candidate.get("geo") or {}
    lat, lon = geo.get("lat"), geo.get("lon")
    if lat is None or lon is None:
        return None
    try:
        return _haversine_km(TLV[0], TLV[1], float(lat), float(lon))
    except (TypeError, ValueError):
        logger.debug("Invalid geo coordinates for candidate %s", candidate.get("name"))
        return None


def _compute_candidate_meta(
    candidate: Dict[str, Any],
    semantic_norm: float,
    prefs: Dict[str, Any],
    travel_limit_km: float | None,
    distance_km: float | None,
) -> Tuple[float, List[str], float | None]:
    reasons: List[str] = []
    distance_norm = 0.5

    if distance_km is not None:
        max_radius = travel_limit_km or DEFAULT_RADIUS_KM
        distance_norm = max(0.0, 1.0 - min(distance_km, max_radius) / max_radius)
        reasons.append(f"~{distance_km:.1f} km away")
        if travel_limit_km is not None and distance_km <= travel_limit_km:
            reasons.append(f"Within your {travel_limit_km:g} km travel limit")

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
    raw = search_providers(es, q, lat=TLV[0], lon=TLV[1], radius_km=DEFAULT_RADIUS_KM)
    logger.debug(f"Raw provider search results: {raw}")

    prefs: Dict[str, Any] = dict(state.get("preferences") or {})
    travel_limit_km = _get_travel_limit(prefs)

    best: Dict[Tuple[str, str], Tuple[Dict[str, Any], float | None]] = {}
    for c in raw:
        name = c.get("name")
        phone = c.get("phone")
        if not name or not phone:
            continue
        key = (name, phone)
        candidate = c.copy()
        distance_km = _candidate_distance(candidate)
        pair = (candidate, distance_km)
        existing = best.get(key)
        if existing is None or _should_replace_candidate(
            existing, pair, travel_limit_km
        ):
            best[key] = pair

    candidates_with_distance = list(best.values())

    if travel_limit_km is not None:
        filtered: list[Tuple[Dict[str, Any], float | None]] = []
        for candidate, distance_km in candidates_with_distance:
            if distance_km is not None and distance_km > travel_limit_km:
                logger.debug(
                    "Filtered provider %s at %.2f km beyond travel limit %.2f km",
                    candidate.get("name"),
                    distance_km,
                    travel_limit_km,
                )
                continue
            filtered.append((candidate, distance_km))
        candidates_with_distance = filtered

    semantic_scores = [c.get("_score", 0.0) for c, _ in candidates_with_distance]
    semantic_norms = _normalize(semantic_scores)
    if not semantic_norms:
        semantic_norms = [1.0 for _ in candidates_with_distance]

    ranked: list[Dict[str, Any]] = []
    for (candidate, distance_km), sem_norm in zip(
        candidates_with_distance, semantic_norms
    ):
        score, reasons, distance_km = _compute_candidate_meta(
            candidate, sem_norm, prefs, travel_limit_km, distance_km
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
