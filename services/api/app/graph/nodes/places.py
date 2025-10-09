from __future__ import annotations

import logging
import math
import os
import re
from typing import Any, Dict, List, Tuple, Set

from app.graph.state import BodyState
from app.graph.nodes.rationale_codes import (
    HOURS_MATCH,
    TRAVEL_WITHIN_LIMIT,
    PREFERRED_KIND,
    INSURANCE_MATCH,
)
from app.tools.geo_tools import search_providers
from app.tools.es_client import get_es_client

logger = logging.getLogger(__name__)

# Dummy location for demo (Tel Aviv center). Replace with user-permitted geolocation
TLV = (32.0853, 34.7818)
DEFAULT_RADIUS_KM = 10.0

DEFAULT_WEIGHTS = {
    "semantic": 0.6,
    "distance": 0.25,
    "hours": 0.15,
    "insurance": 0.0,
}

WINDOW_RANGES = {
    "morning": range(5, 12),
    "afternoon": range(12, 17),
    "evening": range(17, 24),
}


def _extract_plan_map(value: Any) -> tuple[Dict[str, str], str | None]:
    plans: Dict[str, str] = {}
    display: str | None = None
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned:
            key = cleaned.lower()
            plans[key] = cleaned
            display = cleaned
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            if not isinstance(item, str):
                continue
            cleaned = item.strip()
            if not cleaned:
                continue
            key = cleaned.lower()
            if key not in plans:
                plans[key] = cleaned
                if display is None:
                    display = cleaned
    return plans, display


def _get_scoring_weights() -> Dict[str, float]:
    weights = DEFAULT_WEIGHTS.copy()
    raw = os.getenv("PREFERENCE_SCORING_WEIGHTS")
    if not raw:
        return weights

    parsed: Dict[str, float] = {}
    for chunk in raw.split(","):
        if ":" not in chunk:
            continue
        key, value = chunk.split(":", 1)
        norm_key = key.strip().lower()
        if norm_key not in weights:
            continue
        try:
            val = float(value)
        except ValueError:
            continue
        if val >= 0:
            parsed[norm_key] = val

    if not parsed:
        return weights

    for key, val in parsed.items():
        weights[key] = val

    total = sum(weights.values())
    if total <= 0:
        logger.warning(
            "Invalid PREFERENCE_SCORING_WEIGHTS provided (%s); using defaults.", raw
        )
        return DEFAULT_WEIGHTS.copy()

    return {key: weights[key] / total for key in weights}


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
    weights: Dict[str, float],
) -> Tuple[float, List[str], float | None, Set[str]]:
    reasons: List[str] = []
    reason_codes: Set[str] = set()
    distance_norm = 0.5
    candidate.pop("matched_insurance_label", None)

    if distance_km is not None:
        max_radius = travel_limit_km or DEFAULT_RADIUS_KM
        distance_norm = max(0.0, 1.0 - min(distance_km, max_radius) / max_radius)
        reasons.append(f"~{distance_km:.1f} km away")
        if travel_limit_km is not None and distance_km <= travel_limit_km:
            reasons.append(f"Within your {travel_limit_km:g} km travel limit")
            reason_codes.add(TRAVEL_WITHIN_LIMIT)
    elif travel_limit_km is not None:
        reason_codes.add(TRAVEL_WITHIN_LIMIT)

    hours_fit = 0.5
    pref_window = prefs.get("hours_window")
    windows = _hours_windows(candidate.get("hours", "") or "")
    if pref_window:
        if windows and pref_window in windows:
            hours_fit = 1.0
            reasons.append(f"Open during {pref_window}")
            reason_codes.add(HOURS_MATCH)
        else:
            hours_fit = 0.0

    preferred_kinds = {k.lower() for k in prefs.get("preferred_kinds", [])}
    kind = (candidate.get("kind") or "").lower()
    if preferred_kinds and kind in preferred_kinds:
        semantic_norm = min(1.0, semantic_norm + 0.1)
        reasons.append(f"Matches preferred kind ({kind})")
        reason_codes.add(PREFERRED_KIND)

    insurance_fit = 0.5
    pref_plans_map, pref_display = _extract_plan_map(prefs.get("insurance_plan"))
    candidate_plans_map, candidate_display = _extract_plan_map(
        candidate.get("insurance_plans") or candidate.get("insurance")
    )
    if pref_plans_map:
        if candidate_plans_map:
            matches = set(pref_plans_map) & set(candidate_plans_map)
            if matches:
                insurance_fit = 1.0
                reason_codes.add(INSURANCE_MATCH)
                match_key = sorted(matches)[0]
                plan_label = (
                    pref_plans_map.get(match_key)
                    or candidate_plans_map.get(match_key)
                    or pref_display
                    or candidate_display
                )
                if plan_label:
                    candidate["matched_insurance_label"] = plan_label
                    reasons.append(f"Accepts your {plan_label} insurance")
            else:
                insurance_fit = 0.0
        else:
            insurance_fit = 0.25

    score = (
        weights["semantic"] * semantic_norm
        + weights["distance"] * distance_norm
        + weights["hours"] * hours_fit
        + weights["insurance"] * insurance_fit
    )
    return score, reasons, distance_km, reason_codes


def run(state: BodyState, es_client=None) -> BodyState:
    es = es_client if es_client else get_es_client()
    q = state.get("user_query_redacted", state.get("user_query", ""))
    logger.debug(f"Searching providers for query: {q}")
    raw = search_providers(es, q, lat=TLV[0], lon=TLV[1], radius_km=DEFAULT_RADIUS_KM)
    logger.debug(f"Raw provider search results: {raw}")

    prefs: Dict[str, Any] = dict(state.get("preferences") or {})
    travel_limit_km = _get_travel_limit(prefs)
    weights = _get_scoring_weights()

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
        score, reasons, distance_km, reason_codes = _compute_candidate_meta(
            candidate, sem_norm, prefs, travel_limit_km, distance_km, weights
        )
        cand_with_meta = candidate.copy()
        cand_with_meta["score"] = round(score, 4)
        if distance_km is not None:
            cand_with_meta["distance_km"] = round(distance_km, 2)
        cand_with_meta["reasons"] = reasons
        if reason_codes:
            cand_with_meta["reason_codes"] = list(reason_codes)
        ranked.append(cand_with_meta)

    ranked.sort(key=lambda c: c.get("score", 0.0), reverse=True)
    state["candidates"] = ranked
    logger.debug(f"Final candidates after scoring: {state['candidates']}")
    return state
