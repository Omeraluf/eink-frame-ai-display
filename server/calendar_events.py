"""Upcoming events from a Google Calendar secret iCal link."""
import datetime as dt
import os
import tomllib
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

import icalendar
import recurring_ical_events

SECRETS = Path(__file__).resolve().parent / "secrets.toml"


@dataclass
class Event:
    title: str
    start: dt.datetime  # local time; midnight for all-day events
    all_day: bool


def ical_url() -> str | None:
    """From an env var (GitHub Actions) or server/secrets.toml (local)."""
    url = os.environ.get("GOOGLE_ICAL_URL")
    if not url and SECRETS.exists():
        url = tomllib.loads(SECRETS.read_text()).get("google_calendar", {}).get("ical_url")
    return url if url and "PASTE" not in url else None


def fetch(start: dt.datetime, days: int, tz: ZoneInfo) -> list[Event] | None:
    """Events from `start` until `days` later, sorted. None if the calendar is unreachable."""
    url = ical_url()
    if url is None:
        print("Calendar: no iCal link configured")
        return None
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            cal = icalendar.Calendar.from_ical(resp.read())
        events = []
        for ev in recurring_ical_events.of(cal).between(start, start + dt.timedelta(days=days)):
            begin = ev["DTSTART"].dt
            all_day = not isinstance(begin, dt.datetime)
            if all_day:
                begin = dt.datetime.combine(begin, dt.time(), tz)
            else:
                begin = begin.astimezone(tz)
                if begin < start:
                    continue  # already started before the frame is shown
            events.append(Event(str(ev.get("SUMMARY", "")).strip(), begin, all_day))
        return sorted(events, key=lambda e: e.start)
    except Exception as e:
        print(f"Calendar unavailable: {e}")
        return None


def most_important(events: list[Event], now: dt.datetime, cfg: dict) -> Event | None:
    """An event marked important (e.g. "!" in the title) within the lookahead window;
    otherwise the next timed event today or tomorrow; otherwise nothing."""
    marker = cfg["important_marker"]
    marked = [e for e in events if marker in e.title]
    if marked:
        return marked[0]
    day_after_tomorrow = dt.datetime.combine(now.date() + dt.timedelta(days=2), dt.time(), now.tzinfo)
    timed = [e for e in events if not e.all_day and e.start < day_after_tomorrow]
    return timed[0] if timed else None


def when(e: Event, now: dt.datetime) -> str:
    days = (e.start.date() - now.date()).days
    day = "Today" if days == 0 else "Tomorrow" if days == 1 else e.start.strftime("%a")
    return day if e.all_day else f"{day} {e.start:%H:%M}"


def clean_title(e: Event, cfg: dict) -> str:
    """Marker removed, whitespace collapsed (titles can contain line breaks), capped in length.
    The frame layout shortens it further if the line is too wide."""
    title = " ".join(e.title.replace(cfg["important_marker"], "").split())
    return title[: cfg["max_chars"]].rstrip()


def event_line(e: Event, now: dt.datetime, cfg: dict) -> str:
    return f"{when(e, now)} · {clean_title(e, cfg)}"


def week_lines(events: list[Event], now: dt.datetime, cfg: dict) -> list[str]:
    """One line per event, "Tue 14:00 Dentist", up to `max_lines`."""
    return [f"{when(e, now)}  {clean_title(e, cfg)}" for e in events[: cfg["max_lines"]]]
