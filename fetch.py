"""The five PeopleTray calls the dashboard needs."""
from datetime import timedelta

import peopletray
from periods import add_months, reporting_month

PATHS = {
    "events": "/api/v2/powerbi/events",
    "injuries": "/api/v2/powerbi/eventinjurylist",
    "hours": "/api/v2/powerbi/exposurehours",
    "actions": "/api/v2/powerbi/actions",
    "people": "/api/v2/powerbi/people",
}
_UNDATED = ("people",)
# Feeds that are never legitimately empty; an empty one means PeopleTray is not answering properly.
_CORE = ("events", "hours", "people")
# Every field the dashboard reads, as seen in the live feeds on 2026-10-11. A renamed
# field would otherwise read as blank and quietly zero a figure.
REQUIRED_KEYS = {
    "events": ("eventId", "eventDateTime", "eventDate", "workGroup", "eventType",
               "eventSubType", "injuryType", "eventStatus"),
    "injuries": ("eventId", "injuryType", "eventSubTypeName", "returnWorkDate",
                 "injuryBodyLocation", "injuryNature", "injuryMechanism"),
    "hours": ("groupName", "year", "month", "exposureHours"),
    "actions": ("actionStatus", "dueDate", "completedDate", "assignee", "requiredAction",
                "createdDate"),
    "people": ("workGroup", "employer", "emplpyeeType", "dateCommenced", "dateCeased"),
}


def fetch_all(today, get=peopletray.get):
    # The oldest trend point is 11 months back and needs its own 12 months behind it.
    first = add_months(reporting_month(today), -22)
    window = {"fromDate": f"{first[0]}-{first[1]:02d}-01",
              "toDate": (today + timedelta(days=1)).isoformat()}
    # Actions are fetched in full: the overdue history ranks actionees over all time.
    windows = {name: window for name in PATHS}
    windows["actions"] = dict(window, fromDate="2020-01-01")
    raw = {name: get(path, None if name in _UNDATED else windows[name]) for name, path in PATHS.items()}
    for name, rows in raw.items():
        # An error object or an empty answer with HTTP 200 must not become an empty dashboard.
        if not isinstance(rows, list):
            raise ValueError(f"PeopleTray returned {type(rows).__name__}, not a list, for {name}")
        if not rows and name in _CORE:
            raise ValueError(f"PeopleTray returned no rows for {name}")
        missing = [key for key in REQUIRED_KEYS[name] if rows and key not in rows[0]]
        if missing:
            raise ValueError(f"PeopleTray {name} rows no longer carry: {', '.join(missing)}")
    return raw
