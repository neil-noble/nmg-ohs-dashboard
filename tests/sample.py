"""Synthetic PeopleTray data shaped like the real feeds. Every name here is invented."""
from datetime import date

TODAY = date(2026, 10, 11)
MONTH = (2026, 9)
FAKE_NAME = "Zebedee Quixote"


def event(event_id, day, workgroup, event_type, sub_type=None, injury_type="",
          status="Closed and Saved"):
    return {
        "eventId": event_id, "eventDateTime": f"{day}T08:00:00", "eventDate": "",
        "workGroup": workgroup, "eventType": event_type, "eventSubType": sub_type,
        "injuryType": injury_type, "eventStatus": status,
        "reportedBy": FAKE_NAME, "person": FAKE_NAME,
        "shortDescription": "Quixote slipped near the workshop", "location": "Workshop bay 3",
    }


def injury(event_id, **fields):
    row = {"eventId": event_id, "injuryType": None, "eventSubTypeName": "",
           "returnWorkDate": None, "injuryBodyLocation": None, "injuryNature": None,
           "injuryMechanism": None, "personInjuredName": FAKE_NAME}
    row.update(fields)
    return row


def hours(workgroup, year, month, value):
    return {"groupName": workgroup, "year": year, "month": month,
            "exposureHours": value, "numberOfTeamMembers": 0}


def person(workgroup, employer="New Murchison Gold Ltd", kind="Full time",
           commenced="2025-01-01T00:00:00", ceased=None):
    return {"firstName": "Zebedee", "lastName": "Quixote", "workGroup": workgroup,
            "employer": employer, "emplpyeeType": kind,
            "dateCommenced": commenced, "dateCeased": ceased}


def action(status, due=None, completed=None, assignee=FAKE_NAME,
           required="Quixote to replace the guard", created="2026-09-01T00:00:00",
           workgroup="CPO - Ozland", reminder=2):
    return {"actionStatus": status, "dueDate": due, "completedDate": completed,
            "assignee": assignee, "requiredAction": required, "createdDate": created,
            "assigneeWorkgroup": workgroup, "reminderDays": reminder}


def checklist(name, status="Open"):
    return {"checklistName": name, "workflowStatus": status, "person": FAKE_NAME, "user": FAKE_NAME}


EVENTS = [
    event(1, "2026-09-11", "CPO - Ozland", "Injury", "First Aid Injury", "FAI (First Aid Injury) "),
    event(2, "2026-09-16", "CPO - Ozland", "Injury", "First Aid Injury", ""),
    event(3, "2026-08-14", "GG - Exploration", "Injury", "Medical Treatment Injury", "LTI (Lost Time Injury) "),
    event(4, "2026-08-25", "CPO - Ozland", "Injury", "No Treatment Required", "NWR (Non Work Related) "),
    event(5, "2026-09-05", "CPO - Tech Services", "Near Miss", "Near Miss (Other)"),
    event(6, "2026-09-20", "CPO - MLG", "Near Miss", "Near Miss (Other)", status="Open Workflow"),
    event(7, "2026-09-27", "CPO - Ozland", "Property Damage / Loss"),
    event(8, "2026-07-25", "GG - Exploration", "Violence"),
    event(9, "2026-08-02", "Contractors - Other", "Security"),
    event(10, "2026-09-03", "Flight/Accommodation ONLY", "Property Damage / Loss"),
    event(11, "2026-09-04", "Shutdown Crew", "Procedural Compliance"),
    event(12, "2026-06-10", "CPO - Geology", "Injury", "No Treatment Required", ""),
    event(13, "2026-08-26", "CPO - Ozland", "Non Work Related"),
    event(14, "2026-09-09", "CPO - Ozland", "Misfire"),
]

INJURIES = [
    injury(1, injuryBodyLocation="Back", injuryNature="Superficial injury",
           injuryMechanism="Other muscular stress"),
    injury(3, injuryBodyLocation="Hands and fingers"),
]

HOURS = (
    [hours("CPO - Ozland", 2026, 9, 30000.0), hours("Contractors - Local", 2026, 9, 500.0),
     hours("GG - Exploration", 2026, 9, 2000.0), hours("Drilling Contractors", 2026, 9, 1000.0),
     hours("Flight/Accommodation ONLY", 2026, 9, 2500.0), hours("PER - Management", 2026, 9, 40.0),
     hours("CPO - Ozland", 2026, 8, 31000.0), hours("GG - Exploration", 2026, 8, 2000.0),
     hours("CPO - Ozland", 2026, 7, 29000.0), hours("GG - Exploration", 2026, 7, 1500.0)]
    + [hours("CPO - Ozland", y, m, 20000.0) for y, m in
       [(2025, 10), (2025, 11), (2025, 12), (2026, 1), (2026, 2), (2026, 3), (2026, 4), (2026, 5), (2026, 6)]]
    + [hours("GG - Exploration", y, m, 1000.0) for y, m in
       [(2025, 10), (2025, 11), (2025, 12), (2026, 1), (2026, 2), (2026, 3), (2026, 4), (2026, 5), (2026, 6)]]
)

PEOPLE = [
    person("CPO - Geology"),
    person("CPO - Geology"),
    person("CPO - Tech Services", kind="Contractor"),
    person("CPO - Ozland", employer="Ozland Drill and Blast", kind="Contractor"),
    person("GG - Exploration"),
    person("PER - Finance"),
    person("CPO - Management", commenced="2026-10-05T00:00:00"),
    person("GG - Exploration", ceased="2026-09-15T00:00:00"),
]

ACTIONS = [
    action("Open", due="2026-11-01T00:00:00", assignee="Petra  ACTIONEE",
           required="Review the ore mark-up\r\nprocedure"),
    action("Open", due="2026-10-02T00:00:00", assignee="Otto OWNER", required="Fit the <new> guard"),
    action("Closed complete", due="2026-09-10T00:00:00", completed="2026-09-15T02:00:00",
           assignee="Otto OWNER"),
    action("Closed complete", due="2026-08-01T00:00:00", completed="2026-08-01T02:00:00",
           assignee="Petra ACTIONEE", created="2025-07-20T00:00:00"),
]

CHECKLISTS = [
    checklist("Take 5 "), checklist("Take 5"), checklist("Take 5", "Closed (Saved)"),
    checklist("Prestart - Light Vehicles"), checklist("Prestart - Light Vehicles", "Closed (Discarded)"),
    checklist("Uniform Order"),
]

RAW = {"events": EVENTS, "injuries": INJURIES, "hours": HOURS,
       "actions": ACTIONS, "people": PEOPLE, "checklists": CHECKLISTS}
