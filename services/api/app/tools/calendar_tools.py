from datetime import datetime
from pathlib import Path
from pydantic import BaseModel
from app.config import settings


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
    data_dir = Path(settings.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    stamp = event.start.strftime("%Y%m%dT%H%M%S")
    safe_title = "".join([c if c.isalnum() else "_" for c in (event.title or "event")])[
        :40
    ]
    path = data_dir / "calendar_events" / f"{safe_title}_{stamp}.ics"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write(ics)
    return str(path)
