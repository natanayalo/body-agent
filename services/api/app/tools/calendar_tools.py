from datetime import datetime, timedelta
from pydantic import BaseModel


class CalendarEvent(BaseModel):
    title: str
    start: datetime
    end: datetime
    location: str | None = None
    notes: str | None = None


# Stub: write to ICS file (real impl could use CalDAV)
def create_event(event: CalendarEvent) -> str:
    ics = (
        "BEGIN:VCALENDAR\n"
        "VERSION:2.0\n"
        "BEGIN:VEVENT\n"
        f"SUMMARY:{event.title}\n"
        f"DTSTART:{event.start.strftime('%Y%m%dT%H%M%SZ')}\n"
        f"DTEND:{event.end.strftime('%Y%m%dT%H%M%SZ')}\n"
        f"LOCATION:{event.location or ''}\n"
        f"DESCRIPTION:{event.notes or ''}\n"
        "END:VEVENT\nEND:VCALENDAR\n"
    )
    path = "/app/app/data/event.ics"
    import os
    os.makedirs("/app/app/data", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(ics)
    return path
