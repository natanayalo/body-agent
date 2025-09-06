from datetime import datetime
from pydantic import BaseModel
import os


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
    os.makedirs("/app/app/data", exist_ok=True)
    stamp = event.start.strftime("%Y%m%dT%H%M%S")
    safe_title = "".join([c if c.isalnum() else "_" for c in (event.title or "event")])[
        :40
    ]
    path = f"/app/app/data/{safe_title}_{stamp}.ics"
    with open(path, "w", encoding="utf-8") as f:
        f.write(ics)
    return path
