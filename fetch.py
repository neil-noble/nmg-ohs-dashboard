"""The five PeopleTray calls the dashboard needs."""
from datetime import timedelta

import peopletray
from periods import add_months, reporting_month

_DATED = {
    "events": "/api/v2/powerbi/events",
    "injuries": "/api/v2/powerbi/eventinjurylist",
    "hours": "/api/v2/powerbi/exposurehours",
    "actions": "/api/v2/powerbi/actions",
}
_PEOPLE = "/api/v2/powerbi/people"


def fetch_all(today, get=peopletray.get):
    # The oldest trend point is 11 months back and needs its own 12 months behind it.
    first = add_months(reporting_month(today), -22)
    window = {"fromDate": f"{first[0]}-{first[1]:02d}-01",
              "toDate": (today + timedelta(days=1)).isoformat()}
    raw = {name: get(path, window) for name, path in _DATED.items()}
    raw["people"] = get(_PEOPLE, None)
    for name, rows in raw.items():
        if not isinstance(rows, list):
            # An error object with HTTP 200 must not become an empty dashboard.
            raise ValueError(f"PeopleTray returned no list for {name}: {str(rows)[:200]}")
    return raw
