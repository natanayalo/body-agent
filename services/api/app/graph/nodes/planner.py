from datetime import datetime, timedelta, UTC
import logging
import os
from typing import Any, Dict, List

from app.graph.nodes.memory import extract_preferences
from app.graph.nodes.rationale_codes import (
    HOURS_MATCH,
    TRAVEL_WITHIN_LIMIT,
    PREFERRED_KIND,
    INSURANCE_MATCH,
)
from app.graph.state import BodyState, SubIntent
from app.tools.calendar_tools import CalendarEvent, create_event
from app.tools.es_client import get_es_client

logger = logging.getLogger(__name__)


MEDS_INTENT = "meds"
APPOINTMENT_INTENT = "appointment"
PLAN_TYPE_MED_SCHEDULE = "med_schedule"
PLAN_TYPE_NONE = "none"
SUB_INTENT_SCHEDULE: SubIntent = "schedule"

_DEFAULT_LANGUAGE = "en"

RATIONALE_STRINGS = {
    "en": {
        "prefix": "Because ",
        "distance": "it's about {distance_km:.1f} km from you",
        "within_limit": "within your {travel_limit:.1f} km travel limit",
        "travel_limit_only": "honors your {travel_limit:.1f} km travel limit",
        "hours": "open during your preferred {window} hours",
        "preferred_kind": "matches your preferred {kind}",
        "insurance": "accepts your {insurance} insurance",
        "default": "Best match for your saved preferences.",
        "separator": "; ",
        "terminator": ".",
    },
    "he": {
        "prefix": "כי ",
        "distance": 'מרחק של כ-{distance_km:.1f} ק"מ ממך',
        "within_limit": 'בתוך מגבלת הנסיעה של {travel_limit:.1f} ק"מ',
        "travel_limit_only": 'מכבדת מגבלת נסיעה של {travel_limit:.1f} ק"מ',
        "hours": "פתוח במהלך שעות ה{window} שהעדפת",
        "preferred_kind": "מתאים לסוג שהעדפת ({kind})",
        "insurance": "מקבל את ביטוח {insurance} שלך",
        "default": "ההתאמה הטובה ביותר להעדפותיך.",
        "separator": "; ",
        "terminator": ".",
    },
}


def _translate_window(value: str, language: str) -> str:
    window = value.lower()
    labels = {
        "morning": {"en": "morning", "he": "בוקר"},
        "afternoon": {"en": "afternoon", "he": "צהריים"},
        "evening": {"en": "evening", "he": "ערב"},
    }
    return labels.get(window, {}).get(language, window)


def _format_rationale(
    language: str,
    candidate: Dict[str, Any],
    preferences: Dict[str, Any],
) -> str:
    lang = language if language in RATIONALE_STRINGS else _DEFAULT_LANGUAGE
    strings = RATIONALE_STRINGS.get(lang, RATIONALE_STRINGS[_DEFAULT_LANGUAGE])
    distance_km = candidate.get("distance_km")
    prefs = preferences or {}
    fragments: list[str] = []
    reason_codes = {str(reason).lower() for reason in candidate.get("reason_codes", [])}

    def _fmt(limit: float | None) -> float | None:
        if limit is None:
            return None
        try:
            return float(limit)
        except (TypeError, ValueError):
            return None

    travel_limit = _fmt(prefs.get("max_travel_km"))

    if distance_km is not None:
        fragments.append(strings["distance"].format(distance_km=distance_km))
        if travel_limit is not None and TRAVEL_WITHIN_LIMIT in reason_codes:
            fragments.append(strings["within_limit"].format(travel_limit=travel_limit))
    elif travel_limit is not None and TRAVEL_WITHIN_LIMIT in reason_codes:
        fragments.append(strings["travel_limit_only"].format(travel_limit=travel_limit))

    pref_window = (prefs.get("hours_window") or "").lower()
    if pref_window and HOURS_MATCH in reason_codes:
        window_text = _translate_window(pref_window, lang)
        fragments.append(strings["hours"].format(window=window_text))

    candidate_kind_display = candidate.get("kind") or ""
    candidate_kind = (candidate_kind_display or "").lower()
    if PREFERRED_KIND in reason_codes:
        fragments.append(
            strings["preferred_kind"].format(
                kind=candidate_kind_display or candidate_kind
            )
        )

    if INSURANCE_MATCH in reason_codes:

        def _collect(value: Any) -> tuple[dict[str, str], str | None]:
            plans: dict[str, str] = {}
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

        pref_map, pref_display = _collect(prefs.get("insurance_plan"))
        cand_map, cand_display = _collect(
            candidate.get("insurance_plans") or candidate.get("insurance")
        )
        insurance_display = None
        if pref_map and cand_map:
            matches = set(pref_map) & set(cand_map)
            if matches:
                key = sorted(matches)[0]
                insurance_display = pref_map.get(key) or cand_map.get(key)
        if insurance_display is None:
            insurance_display = pref_display or cand_display
        if insurance_display:
            fragments.append(strings["insurance"].format(insurance=insurance_display))

    if not fragments:
        return strings["default"]

    body = strings["separator"].join(fragments)
    sentence = f"{strings['prefix']}{body}"
    terminator = strings.get("terminator", ".")
    if not sentence.endswith(terminator):
        sentence = f"{sentence}{terminator}"
    return sentence


def run(state: BodyState, es_client: Any = None) -> BodyState:
    intent = state.get("intent")
    now = datetime.now(UTC)

    if intent == MEDS_INTENT:
        sub_intent = state.get("sub_intent")
        if sub_intent != SUB_INTENT_SCHEDULE:
            logger.debug(
                "Planner: Suppressing plan for meds sub_intent '%s'", sub_intent
            )
            state["plan"] = {"type": PLAN_TYPE_NONE}
            return state

        # Produce a toy schedule: morning/evening entries for next 24h
        plan = {
            "type": PLAN_TYPE_MED_SCHEDULE,
            "items": [
                {
                    "title": "Morning meds",
                    "time": (now + timedelta(hours=1)).isoformat(),
                },
                {
                    "title": "Evening meds",
                    "time": (now + timedelta(hours=12)).isoformat(),
                },
            ],
        }
        state["plan"] = plan
        return state

    if intent == APPOINTMENT_INTENT:
        logger.debug("Planner: Handling 'appointment' intent.")
        prefs = state.get("preferences") or {}
        if not prefs and (user_id := state.get("user_id")):
            es = es_client if es_client else get_es_client()
            docs = es.search(
                index=os.environ["ES_PRIVATE_INDEX"],
                body={
                    "query": {
                        "bool": {
                            "must": [
                                {"term": {"user_id": user_id}},
                                {"term": {"entity": "preference"}},
                            ]
                        }
                    }
                },
            )
            facts = [hit["_source"] for hit in docs["hits"]["hits"]]
            prefs = extract_preferences(facts)
            if prefs:
                state["preferences"] = prefs
        logger.debug(f"Planner: User preferences: {prefs}")

        candidates: List[Dict[str, Any]] = state.get("candidates", [])
        if not candidates:
            logger.debug("Planner: No candidates available, returning 'none'.")
        else:
            best = candidates[0]
            reasons = best.get("reasons", []) or []
            logger.debug(f"Planner: Best candidate: {best}")

            rationale = _format_rationale(state.get("language", "en"), best, prefs)

            # Pick top candidate and create 1h slot tomorrow at 09:00Z
            start = datetime(now.year, now.month, now.day) + timedelta(days=1, hours=9)
            evt = CalendarEvent(
                title=f"Visit: {best.get('name','Clinic')}",
                start=start,
                end=start + timedelta(hours=1),
                location=best.get("name"),
            )
            path = create_event(evt)
            logger.debug(f"Planner: Event path created: {path}")
            explanations = [rationale] if rationale else []
            explanations.extend(reasons)
            reasons_str = ", ".join(explanations)
            state["plan"] = {
                "type": APPOINTMENT_INTENT,
                "event_path": path,
                "provider": best,
                "reasons": reasons_str,
                "explanations": explanations,
                "rationale": rationale,
            }
            return state

    # Fallback
    logger.debug("Planner: Falling back to 'none' plan.")
    state["plan"] = {"type": PLAN_TYPE_NONE}
    return state
