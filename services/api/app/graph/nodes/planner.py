from datetime import datetime, timedelta, UTC
import logging
import os
from typing import Any, Dict, List

from app.graph.nodes.memory import extract_preferences
from app.graph.state import BodyState
from app.tools.calendar_tools import CalendarEvent, create_event
from app.tools.es_client import get_es_client

logger = logging.getLogger(__name__)


def run(state: BodyState, es_client: Any = None) -> BodyState:
    intent = state.get("intent")
    now = datetime.now(UTC)

    if intent == "meds":
        # Produce a toy schedule: morning/evening entries for next 24h
        plan = {
            "type": "med_schedule",
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

    if intent == "appointment":
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
            explanations = list(reasons)
            reasons_str = ", ".join(explanations)
            state["plan"] = {
                "type": "appointment",
                "event_path": path,
                "provider": best,
                "reasons": reasons_str,
                "explanations": explanations,
            }
            return state

    # Fallback
    logger.debug("Planner: Falling back to 'none' plan.")
    state["plan"] = {"type": "none"}
    return state
