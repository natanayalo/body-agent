from datetime import datetime, timedelta, UTC
import logging
import os
from typing import Any, Dict, List

from app.graph.nodes.memory import extract_preferences
from app.graph.state import BodyState, SubIntent
from app.tools.calendar_tools import CalendarEvent, create_event
from app.tools.es_client import get_es_client

logger = logging.getLogger(__name__)


MEDS_INTENT = "meds"
APPOINTMENT_INTENT = "appointment"
PLAN_TYPE_MED_SCHEDULE = "med_schedule"
PLAN_TYPE_NONE = "none"
SUB_INTENT_SCHEDULE: SubIntent = "schedule"


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
    lang = language if language in {"en", "he"} else "en"
    distance_km = candidate.get("distance_km")
    reasons = candidate.get("reasons", []) or []
    prefs = preferences or {}
    fragments: list[str] = []

    def _fmt(limit: float | None) -> float | None:
        if limit is None:
            return None
        try:
            return float(limit)
        except (TypeError, ValueError):
            return None

    travel_limit = _fmt(prefs.get("max_travel_km"))

    if distance_km is not None:
        if lang == "he":
            fragments.append(f'מרחק של כ-{distance_km:.1f} ק"מ ממך')
        else:
            fragments.append(f"it's about {distance_km:.1f} km from you")
        if travel_limit is not None and distance_km <= travel_limit + 1e-6:
            if lang == "he":
                fragments.append(f'בתוך מגבלת הנסיעה של {travel_limit:.1f} ק"מ')
            else:
                fragments.append(f"within your {travel_limit:.1f} km travel limit")
    elif travel_limit is not None:
        if lang == "he":
            fragments.append(f'מכבדת מגבלת נסיעה של {travel_limit:.1f} ק"מ')
        else:
            fragments.append(f"honors your {travel_limit:.1f} km travel limit")

    pref_window = (prefs.get("hours_window") or "").lower()
    if pref_window and any("Open during" in r for r in reasons):
        window_text = _translate_window(pref_window, lang)
        if lang == "he":
            fragments.append(f"פתוח במהלך שעות ה{window_text} שהעדפת")
        else:
            fragments.append(f"open during your preferred {window_text} hours")

    preferred_kinds = {
        str(k).lower() for k in (prefs.get("preferred_kinds") or []) if str(k).strip()
    }
    candidate_kind = (candidate.get("kind") or "").lower()
    if preferred_kinds and candidate_kind in preferred_kinds:
        if lang == "he":
            fragments.append(f"מתאים לסוג שהעדפת ({candidate_kind})")
        else:
            fragments.append(f"matches your preferred {candidate_kind}")

    if not fragments:
        if lang == "he":
            return "ההתאמה הטובה ביותר להעדפותיך."
        return "Best match for your saved preferences."

    separator = "; "
    body = separator.join(fragments)
    if lang == "he":
        prefix = "כי "
    else:
        prefix = "Because "
    sentence = f"{prefix}{body}"
    return sentence if sentence.endswith(".") else f"{sentence}."


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
