"""The five PeopleTray calls the dashboard needs."""
from datetime import timedelta

import peopletray
from periods import add_months, fy_start, reporting_month

PATHS = {
    "events": "/api/v2/powerbi/events",
    "injuries": "/api/v2/powerbi/eventinjurylist",
    "hours": "/api/v2/powerbi/exposurehours",
    "actions": "/api/v2/powerbi/actions",
    "people": "/api/v2/powerbi/people",
    "checklists": "/api/v2/powerbi/checklistslite",
    "roster": "/api/v2/powerbi/personrosterssinglesite",
    "shifttypes": "/api/v2/powerbi/shifttypes",
    "competencies": "/api/v2/powerbi/personworkrolecompetencycompliance",
}
_UNDATED = ("people", "shifttypes", "competencies")
# Feeds that are never legitimately empty; an empty one means PeopleTray is not answering properly.
_CORE = ("events", "hours", "people")
# Every field the dashboard reads, as seen in the live feeds on 2026-10-11. A renamed
# field would otherwise read as blank and quietly zero a figure.
REQUIRED_KEYS = {
    "events": ("eventId", "eventDateTime", "eventDate", "workGroup", "eventType",
               "eventSubType", "injuryType", "eventStatus", "targetCloseDateTime",
               "reportedTo", "currentStep"),
    "injuries": ("eventId", "injuryType", "eventSubTypeName", "returnWorkDate",
                 "injuryBodyLocation", "injuryNature", "injuryMechanism"),
    "hours": ("groupName", "year", "month", "exposureHours"),
    "actions": ("actionStatus", "dueDate", "completedDate", "assignee", "requiredAction",
                "createdDate", "reminderDays", "assigneeWorkgroup", "assigneeId"),
    "checklists": ("checklistName", "workflowStatus"),
    "people": ("id", "employeeId", "firstName", "lastName", "workGroup", "workRoles", "employer",
               "emplpyeeType", "dateCommenced", "dateCeased"),
    "roster": ("personId", "rosterDate", "shiftTypeId"),
    "shifttypes": ("id", "isDayshift", "isNightshift"),
    "competencies": ("employeeId", "workRole", "competencyName", "competencyStatus",
                     "competencyIssueDate", "competencyExpiryDate"),
}


def _all_pages(get, path, params):
    """A feed's rows. The competency feed is paged (100 a page); the others come back whole."""
    rows = []
    while True:
        answer = get(path, params)
        if not (isinstance(answer, dict) and "data" in answer):
            return answer if not rows else rows + list(answer)
        rows.extend(answer["data"] or [])
        following = answer.get("nextPageLink")
        if not following:
            return rows
        path, params = following.replace(peopletray.BASE_URL, ""), None


def fetch_all(today, get=peopletray.get):
    # The oldest trend point is 11 months back and needs its own 12 months behind it.
    first = add_months(reporting_month(today), -22)
    window = {"fromDate": f"{first[0]}-{first[1]:02d}-01",
              "toDate": (today + timedelta(days=1)).isoformat()}
    # Actions and checklists are fetched in full: the overdue history ranks actionees over
    # all time, and a workflow can sit open for longer than the reporting window.
    windows = {name: window for name in PATHS}
    windows["actions"] = windows["checklists"] = dict(window, fromDate="2020-01-01")
    # Ozland's ERT record runs from the start of the financial year to today.
    fy = fy_start((today.year, today.month))
    windows["roster"] = {"fromDate": f"{fy[0]}-{fy[1]:02d}-01", "toDate": today.isoformat()}
    raw = {name: _all_pages(get, path, None if name in _UNDATED else windows[name])
           for name, path in PATHS.items()}
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
