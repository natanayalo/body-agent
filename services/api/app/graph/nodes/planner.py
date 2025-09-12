from datetime import datetime, timedelta, UTC
from app.graph.state import BodyState
from app.tools.calendar_tools import CalendarEvent, create_event
import os
import logging
from typing import TypedDict, List, Any

logger = logging.getLogger(__name__)


class RankedCandidate(TypedDict):
    score: int
    reasons: List[str]
    cand: dict


# Minimal planner for two demo flows


def run(state: BodyState, es_client: Any) -> BodyState:
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
        # Get user preferences from memory
        prefs = {}
        if user_id := state.get("user_id"):
            es = es_client
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
            for d in docs["hits"]["hits"]:
                prefs[d["_source"]["name"]] = d["_source"]["value"]
        logger.debug(f"Planner: User preferences: {prefs}")

        # Rank candidates
        ranked_candidates = []
        for cand in state.get("candidates", []):
            score = 0
            reasons: List[str] = []
            if prefs.get("preferred_kind") == cand.get("kind"):
                score += 1
                reasons.append("preferred kind")
            if (pref_hours := prefs.get("preferred_hours")) and (
                cand_hours := cand.get("hours")
            ):
                if pref_hours in cand_hours.lower():
                    score += 1
                    reasons.append(f"preferred hours: {prefs.get('preferred_hours')}")

            ranked_candidate: RankedCandidate = {
                "score": score,
                "reasons": reasons,
                "cand": cand,
            }
            ranked_candidates.append(ranked_candidate)

        ranked_candidates.sort(key=lambda x: x["score"], reverse=True)

        best_cand = ranked_candidates[0]["cand"] if ranked_candidates else None
        reasons = ranked_candidates[0]["reasons"] if ranked_candidates else []
        logger.debug(f"Planner: Best candidate: {best_cand}")

        # Pick top candidate and create 1h slot tomorrow at 09:00Z
        if best_cand is not None:
            cand = best_cand
            start = datetime(now.year, now.month, now.day) + timedelta(days=1, hours=9)
            evt = CalendarEvent(
                title=f"Visit: {cand.get('name','Clinic')}",
                start=start,
                end=start + timedelta(hours=1),
                location=cand.get("name"),
            )
            path = create_event(evt)
            logger.debug(f"Planner: Event path created: {path}")
            state["plan"] = {
                "type": "appointment",
                "event_path": path,
                "provider": cand,
                "reasons": ", ".join(reasons),
            }
            return state

    # Fallback
    logger.debug("Planner: Falling back to 'none' plan.")
    state["plan"] = {"type": "none"}
    return state
