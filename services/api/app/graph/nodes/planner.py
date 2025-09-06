from datetime import datetime, timedelta
from app.graph.state import BodyState
from app.tools.calendar_tools import CalendarEvent, create_event


# Minimal planner for two demo flows


def run(state: BodyState) -> BodyState:
    intent = state.get("intent")
    now = datetime.utcnow()

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
        # Pick top candidate and create 1h slot tomorrow at 09:00Z
        if cand := (state.get("candidates") or [{}])[0]:
            start = datetime(now.year, now.month, now.day) + timedelta(days=1, hours=9)
            evt = CalendarEvent(
                title=f"Visit: {cand.get('name','Clinic')}",
                start=start,
                end=start + timedelta(hours=1),
                location=cand.get("name"),
            )
            path = create_event(evt)
            state["plan"] = {
                "type": "appointment",
                "event_path": path,
                "provider": cand,
            }
            return state

    # Fallback
    state["plan"] = {"type": "none"}
    return state
