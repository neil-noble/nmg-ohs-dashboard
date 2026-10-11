# NMG OHS Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A daily-rebuilt static HTML dashboard of NMG health and safety statistics, calculated from PeopleTray, published to GitHub Pages and embedded at `emergencyservicesaustralia.com.au/nmg-ohs`.

**Architecture:** `fetch.py` pulls five PeopleTray endpoints; `metrics.py` (pure functions) turns the raw lists into one `report` dict; `render.py` turns that dict into a single self-contained `docs/index.html`. A GitHub Actions workflow runs the tests, builds the page and pushes it to a public Pages repo that a Wix iframe embeds.

**Tech Stack:** Python 3.12+ standard library only (urllib, json, html, datetime). `pytest` for tests. Inline CSS and inline SVG; no JavaScript.

**Spec:** `docs/superpowers/specs/2026-10-11-nmg-ohs-dashboard-design.md`

## Global Constraints

- Standard library only for `config`, `periods`, `peopletray`, `fetch`, `metrics`, `render`, `generate_dashboard`.
- The PeopleTray key is read from env `PT_API_KEY`, else line 2 of `C:\claude\PeopleTray DAS\reference\PT API Key for NMG.txt`. It is never written into this repo.
- The published page is public: counts and rates only. No names, employee IDs, event descriptions or locations.
- Mining = workgroups starting `CPO - `, plus `Contractors - Local` and `Contractors - Other`. Exploration = workgroups starting `GG - `, plus `Drilling Contractors`. Excluded = `Flight/Accommodation ONLY` and workgroups starting `PER - `.
- Reporting month = last completed calendar month in Perth time (UTC+8, no daylight saving). FYTD starts 1 July.
- TRIFR = (LTI + RWI + MTI) × 1,000,000 ÷ hours and LTIFR = LTI × 1,000,000 ÷ hours, both rolling 12 months, two decimal places, "NA" when hours are zero.
- Zero counts display as "–" (en dash).
- Colours: Navy `#083045`, River `#55848A`, Gold `#927128`, Pale Gold `#B19045`, Sand `#F1DCAA`, Cool Grey `#DBDBD3`, Black 93% `#333334`. Font stack: `"Proxima Nova", Aptos, "Segoe UI", system-ui, sans-serif`. Mining series = Navy, Exploration series = Gold.
- Never publish a page built from partial data: any failed or malformed fetch fails the build.
- Run tests from the project root with `python -m pytest -q`.

## Review Focus

1. An event or hours row whose workgroup is blank or new (matches no bucket rule) must not vanish silently: it is left out of the figures and named in the page's "Unmapped workgroup" notice. (Task 3)
2. A bucket with no hours or no events in a period (e.g. Exploration with zero hours, or the whole of July on 1 August) must show "–" or "NA", never raise `ZeroDivisionError`. (Task 3)
3. A build run in January must report December of the previous year, with FYTD starting the previous July. (Task 2)
4. PeopleTray answering HTTP 200 with a non-list body (an error object) must fail the build rather than render an empty dashboard. (Task 5)
5. Text from PeopleTray containing HTML characters (an event type such as `Fire & <Explosion>`) must be escaped on the page. (Task 6)

## File Structure

| File | Responsibility |
|---|---|
| `config.py` | Neil's rules: buckets, injury classes, event-row mapping, colours |
| `periods.py` | Month arithmetic, financial year, Perth "today", date parsing |
| `metrics.py` | Raw PeopleTray lists → `report` dict |
| `peopletray.py` | Authenticated GET with retries |
| `fetch.py` | The five calls and the date window |
| `render.py` | `report` dict → HTML string |
| `generate_dashboard.py` | Entry point |
| `assets/nmg_logo.png` | Downscaled NMG logo, embedded as base64 |
| `tests/sample.py` | Synthetic PeopleTray data (invented names only) |
| `tests/test_*.py` | One test file per module |
| `.github/workflows/dashboard.yml` | Test, build, publish |
| `reference/peopletray_ohs.yaml` | Endpoint facts verified 2026-10-11 |

---

### Task 1: Project setup and `config.py`

**Files:**
- Create: `config.py`, `tests/__init__.py` (empty), `tests/test_config.py`, `pytest.ini`, `reference/peopletray_ohs.yaml`
- Modify: `.gitignore`, `state.yaml`

**Interfaces:**
- Produces: `config.bucket(workgroup) -> str` returning `config.MINING`, `config.EXPLORATION`, `config.EXCLUDED` or `config.UNMAPPED`; `config.classify_injury(injury_type, sub_type) -> str` returning one of `"LTI" "RWI" "MTI" "FAI" "NT" "NWR" "PEC"` or `config.UNCLASSIFIED`; `config.event_row(event_type) -> str | None`; constants `BUCKETS`, `INJURY_CLASSES`, `RECORDABLE`, `NOT_COUNTED`, `INJURY_TYPE`, `FIXED_EVENT_ROWS`, `NEAR_MISS_ROW`, `NMG_EMPLOYER`, `FY_START_MONTH`, `SERIES_COLOURS`, `TREND_GROUPS`, `TREND_COLOURS`.

- [ ] **Step 1: Run ruflo init and fix its model pin**

```bash
cd "/c/claude/NMG OHS Dashboard"
ruflo init --minimal --no-global --no-signup --no-skills-sh
```

Then open `.claude/settings.json` and delete the top-level `"model": "claude-sonnet-5"` line if present (leave `claudeFlow.modelPreferences` alone). Confirm `CLAUDE.md` is still the 4-line bootstrap (`git diff CLAUDE.md` shows nothing).

- [ ] **Step 2: Write `pytest.ini`, extend `.gitignore`**

`pytest.ini`:

```ini
[pytest]
testpaths = tests
pythonpath = .
```

Append to `.gitignore`:

```
# Build output - published to nmg-ohs-site by the workflow, not kept here
docs/index.html
```

- [ ] **Step 3: Write `reference/peopletray_ohs.yaml`**

```yaml
# PeopleTray OHS endpoints - facts verified live 2026-10-11
source: https://api-peopletray.azurewebsites.net
auth: {header: X-API-Key, key_file: "C:\\claude\\PeopleTray DAS\\reference\\PT API Key for NMG.txt", key_is_on: line 2}
swagger: /swagger/docs/v1   # 217 paths
endpoints:
  /api/v2/powerbi/events:          {params: [fromDate, toDate], rows_jul25_sep26: 138}
  /api/v2/powerbi/eventinjurylist: {params: [fromDate, toDate], note: one row per event incl. non-injury events}
  /api/v2/powerbi/exposurehours:   {params: [fromDate, toDate], fields: [groupName, month, year, exposureHours, numberOfTeamMembers], history_from: 2025-07}
  /api/v2/powerbi/actions:         {params: [fromDate, toDate], status_values: [Open, Closed complete, Closed partially complete, Closed non implemented]}
  /api/v2/powerbi/people:          {params: [], rows: 372, note: unpaginated; field is spelt emplpyeeType}
  /api/v2/powerbi/incidentlist:    {status: returns 0 rows - not used}
traps:
  - events.eventDate is dd-mm-yyyy; eventDateTime is ISO - use eventDateTime
  - injuryType has a trailing space, e.g. "FAI (First Aid Injury) "
  - injuryType and eventSubType often disagree (Aug 2026 LTI has subtype Medical Treatment Injury)
  - eventStatus values: "Closed and Saved", "Open Workflow"
  - exposure hours cannot be reconciled to Neil's old spreadsheet (its Exploration 5,277 is not a multiple of 6)
event_types_seen: [Property Damage / Loss, Injury, Procedural Compliance, Near Miss, Production Loss, Non Work Related, Misfire, Violence, Security, Business / Operational Interruption, Community / Heritage]
nmg_head_count_2026_10_11: {Mining: 22, Exploration: 16, rule: "employer == New Murchison Gold Ltd and emplpyeeType != Contractor, Perth excluded"}
```

- [ ] **Step 4: Write the failing tests**

`tests/test_config.py`:

```python
import pytest

import config


@pytest.mark.parametrize("workgroup, expected", [
    ("CPO - Ozland", config.MINING),
    ("CPO - Management - Contractors/Visitors", config.MINING),
    ("Contractors - Local", config.MINING),
    ("Contractors - Other", config.MINING),
    ("GG - Exploration", config.EXPLORATION),
    ("GG - Exploration Contractors", config.EXPLORATION),
    ("Drilling Contractors", config.EXPLORATION),
    ("Flight/Accommodation ONLY", config.EXCLUDED),
    ("PER - Finance", config.EXCLUDED),
    ("  CPO - Geology  ", config.MINING),
    ("Shutdown Crew", config.UNMAPPED),
    ("", config.UNMAPPED),
    (None, config.UNMAPPED),
])
def test_bucket(workgroup, expected):
    assert config.bucket(workgroup) == expected


@pytest.mark.parametrize("injury_type, sub_type, expected", [
    ("LTI (Lost Time Injury) ", "Medical Treatment Injury", "LTI"),   # injury type wins
    ("FAI (First Aid Injury) ", "No Treatment Required", "FAI"),
    ("", "First Aid Injury", "FAI"),                                  # blank falls back
    (None, "No Treatment Required", "NT"),
    (None, "Medical Treatment Injury", "MTI"),
    (None, "Restricted Work Injury", "RWI"),
    (None, "Lost Time Injury", "LTI"),
    ("NWR (Non Work Related) ", "No Treatment Required", "NWR"),
    ("PEC (Pre-Existing Condition) ", "First Aid Injury", "PEC"),
    ("mti (medical treatment injury)", None, "MTI"),
    ("", "", config.UNCLASSIFIED),
    ("Something new", "Something else", config.UNCLASSIFIED),
])
def test_classify_injury(injury_type, sub_type, expected):
    assert config.classify_injury(injury_type, sub_type) == expected


@pytest.mark.parametrize("event_type, expected", [
    ("Near Miss", "Near Miss"),
    ("Violence", "Security Incident / Violence"),
    ("Security", "Security Incident / Violence"),
    ("Environmental Incident", "Environmental Incidents"),
    ("Property Damage / Loss", "Property Damage / Loss"),
    ("Non Work Related", None),
    ("Brand New Type", "Brand New Type"),
    ("", "Unspecified event type"),
    (None, "Unspecified event type"),
])
def test_event_row(event_type, expected):
    assert config.event_row(event_type) == expected
```

- [ ] **Step 5: Run the tests to verify they fail**

Run: `python -m pytest tests/test_config.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'config'`

- [ ] **Step 6: Write `config.py`**

```python
"""The rules Neil set for the NMG OHS dashboard. No I/O and no arithmetic here."""

FY_START_MONTH = 7
NMG_EMPLOYER = "New Murchison Gold Ltd"

MINING, EXPLORATION = "Mining", "Exploration"
BUCKETS = (MINING, EXPLORATION)
EXCLUDED, UNMAPPED = "excluded", "unmapped"

# (result, workgroup prefixes, exact workgroup names). Decided by Neil 2026-10-11.
_BUCKET_RULES = (
    (MINING, ("CPO - ",), ("Contractors - Local", "Contractors - Other")),
    (EXPLORATION, ("GG - ",), ("Drilling Contractors",)),
    (EXCLUDED, ("PER - ",), ("Flight/Accommodation ONLY",)),
)


def bucket(workgroup):
    name = (workgroup or "").strip()
    for result, prefixes, exact in _BUCKET_RULES:
        if name in exact or name.startswith(prefixes):
            return result
    return UNMAPPED


INJURY_TYPE = "Injury"
INJURY_CLASSES = (
    ("LTI", "Lost Time Injury"),
    ("RWI", "Restricted Work Injury"),
    ("MTI", "Medically Treated Injury"),
    ("FAI", "First Aid Injury"),
    ("NT", "No Treatment Injury"),
)
RECORDABLE = ("LTI", "RWI", "MTI")
NOT_COUNTED = ("NWR", "PEC")      # non work related, pre-existing condition
UNCLASSIFIED = "Unclassified injury"

_INJURY_CODES = tuple(code for code, _ in INJURY_CLASSES) + NOT_COUNTED
_SUBTYPE_CLASS = {
    "lost time injury": "LTI",
    "restricted work injury": "RWI",
    "medical treatment injury": "MTI",
    "first aid injury": "FAI",
    "no treatment required": "NT",
}


def classify_injury(injury_type, sub_type):
    """PeopleTray's injury type decides; a blank or unknown one falls back to the sub-type."""
    code = (injury_type or "").strip().split(" ")[0].upper()
    if code in _INJURY_CODES:
        return code
    return _SUBTYPE_CLASS.get((sub_type or "").strip().lower(), UNCLASSIFIED)


NEAR_MISS_ROW = "Near Miss"
ENVIRONMENT_ROW = "Environmental Incidents"
SECURITY_ROW = "Security Incident / Violence"
HIDDEN_EVENT_TYPES = ("Non Work Related",)
FIXED_EVENT_ROWS = (
    ENVIRONMENT_ROW,
    "Production Loss",
    "Procedural Compliance",
    "Property Damage / Loss",
    SECURITY_ROW,
    "Business / Operational Interruption",
    "Misfire",
    "Community / Heritage",
)


def event_row(event_type):
    """Table row a non-injury event counts under; None for types the report does not show."""
    name = (event_type or "").strip()
    if name in HIDDEN_EVENT_TYPES:
        return None
    if name in ("Violence", "Security"):
        return SECURITY_ROW
    if "environment" in name.lower():
        return ENVIRONMENT_ROW
    return name or "Unspecified event type"


NAVY, RIVER, GOLD, PALE_GOLD = "#083045", "#55848A", "#927128", "#B19045"
SAND, COOL_GREY, BLACK = "#F1DCAA", "#DBDBD3", "#333334"
SERIES_COLOURS = {MINING: NAVY, EXPLORATION: GOLD}

TREND_GROUPS = ("Injury", NEAR_MISS_ROW, "Property Damage / Loss",
                "Procedural Compliance", "Production Loss", "Other")
TREND_COLOURS = (NAVY, RIVER, GOLD, "#D8C8A2", "#8498A2", "#99999A")
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `python -m pytest tests/test_config.py -q`
Expected: `34 passed`

- [ ] **Step 8: Update `state.yaml` and commit**

In `state.yaml` change `phase: spec_review` to `phase: build`, and remove `ruflo init` from `pending_setup`.

```bash
git add -A
git commit -m "Add project setup and config rules"
```

---

### Task 2: `periods.py`

**Files:**
- Create: `periods.py`, `tests/test_periods.py`

**Interfaces:**
- Consumes: `config.FY_START_MONTH`
- Produces: months are `(year, month)` tuples. `today_perth() -> date`, `now_label() -> str`, `add_months(ym, n) -> ym`, `reporting_month(today: date) -> ym`, `fy_start(ym) -> ym`, `month_range(first, last) -> list[ym]` (inclusive), `rolling_12(ym) -> list[ym]`, `month_end(ym) -> date`, `short_label(ym) -> "Sep 26"`, `long_label(ym) -> "September 2026"`, `parse_day(value) -> date | None`.

- [ ] **Step 1: Write the failing tests**

`tests/test_periods.py`:

```python
from datetime import date

import periods


def test_reporting_month_is_last_completed_month():
    assert periods.reporting_month(date(2026, 10, 11)) == (2026, 9)
    assert periods.reporting_month(date(2026, 10, 1)) == (2026, 9)
    assert periods.reporting_month(date(2026, 11, 1)) == (2026, 10)


def test_reporting_month_in_january_is_previous_december():
    assert periods.reporting_month(date(2027, 1, 15)) == (2026, 12)


def test_fy_start():
    assert periods.fy_start((2026, 9)) == (2026, 7)
    assert periods.fy_start((2026, 7)) == (2026, 7)
    assert periods.fy_start((2026, 6)) == (2025, 7)
    assert periods.fy_start((2026, 12)) == (2026, 7)
    assert periods.fy_start((2027, 1)) == (2026, 7)


def test_add_months_crosses_years():
    assert periods.add_months((2026, 9), -11) == (2025, 10)
    assert periods.add_months((2026, 12), 1) == (2027, 1)
    assert periods.add_months((2026, 1), -1) == (2025, 12)


def test_month_range_and_rolling_12():
    assert periods.month_range((2026, 7), (2026, 9)) == [(2026, 7), (2026, 8), (2026, 9)]
    rolling = periods.rolling_12((2026, 9))
    assert len(rolling) == 12
    assert rolling[0] == (2025, 10) and rolling[-1] == (2026, 9)


def test_month_end_and_labels():
    assert periods.month_end((2026, 9)) == date(2026, 9, 30)
    assert periods.month_end((2028, 2)) == date(2028, 2, 29)
    assert periods.short_label((2026, 9)) == "Sep 26"
    assert periods.long_label((2026, 9)) == "September 2026"


def test_parse_day_handles_both_peopletray_formats():
    assert periods.parse_day("2026-09-28T17:10:00") == date(2026, 9, 28)
    assert periods.parse_day("28-09-2026") == date(2026, 9, 28)
    assert periods.parse_day("2026-09-28") == date(2026, 9, 28)
    assert periods.parse_day("") is None
    assert periods.parse_day(None) is None
    assert periods.parse_day("not a date") is None
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_periods.py -q`
Expected: `ModuleNotFoundError: No module named 'periods'`

- [ ] **Step 3: Write `periods.py`**

```python
"""Month arithmetic. A month is a (year, month) tuple throughout the project."""
import calendar
from datetime import date, datetime, timedelta, timezone

import config

# Perth is UTC+8 all year. A fixed offset avoids needing tzdata on Windows.
PERTH = timezone(timedelta(hours=8))


def today_perth():
    return datetime.now(PERTH).date()


def now_label():
    return datetime.now(PERTH).strftime("%d %b %Y, %H:%M AWST").lstrip("0")


def add_months(ym, n):
    index = ym[0] * 12 + ym[1] - 1 + n
    return (index // 12, index % 12 + 1)


def reporting_month(today):
    return add_months((today.year, today.month), -1)


def fy_start(ym):
    year, month = ym
    return (year if month >= config.FY_START_MONTH else year - 1, config.FY_START_MONTH)


def month_range(first, last):
    months, current = [], first
    while current <= last:
        months.append(current)
        current = add_months(current, 1)
    return months


def rolling_12(ym):
    return month_range(add_months(ym, -11), ym)


def month_end(ym):
    return date(ym[0], ym[1], calendar.monthrange(ym[0], ym[1])[1])


def short_label(ym):
    return f"{calendar.month_abbr[ym[1]]} {ym[0] % 100:02d}"


def long_label(ym):
    return f"{calendar.month_name[ym[1]]} {ym[0]}"


def parse_day(value):
    """PeopleTray sends ISO datetimes in most fields but dd-mm-yyyy in events.eventDate."""
    text = (value or "").strip()
    try:
        if len(text) >= 10 and text[2] == "-" and text[5] == "-":
            return date(int(text[6:10]), int(text[3:5]), int(text[0:2]))
        return date.fromisoformat(text[:10])
    except ValueError:
        return None
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_periods.py -q`
Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add periods.py tests/test_periods.py
git commit -m "Add month and financial-year arithmetic"
```

---

### Task 3: `metrics.py` — normalising, the event table and rates

**Files:**
- Create: `tests/sample.py`, `metrics.py`, `tests/test_metrics_table.py`

**Interfaces:**
- Consumes: `config.*`, `periods.*` as defined in Tasks 1–2.
- Produces:
  - `new_issues() -> {"unmapped": set(), "undated": 0}`
  - `normalise_events(events, injuries, issues) -> list[dict]`; each dict has keys `id, day, ym, bucket, row, injury_class, open, return_day, body, nature, mechanism`. `row` is an injury class code, `config.UNCLASSIFIED`, or a table row label. `injury_class` is `None` for non-injury events.
  - `normalise_hours(rows, issues) -> dict[(bucket, ym), float]`
  - `count(events, bucket, months, row) -> int`, `hours_sum(hours, bucket, months) -> float`, `rate(n, hours) -> float | None`, `fmt_count(n) -> str`, `fmt_rate(r) -> str`
  - `frequency_rates(events, hours, bucket, month) -> (trifr, ltifr)` over the rolling 12 months ending `month`
  - `head_count(people, bucket, as_at: date) -> int`
  - `build_table(events, hours, people, month) -> list[{"label": str, "cells": [str, str, str, str], "bold": bool}]`, cells ordered Mining month, Mining FYTD, Exploration month, Exploration FYTD.
  - `tests/sample.py` exposes `RAW` (dict with keys `events, injuries, hours, actions, people`), `TODAY = date(2026, 10, 11)`, `MONTH = (2026, 9)` and builder functions `event, injury, hours, person, action`.

- [ ] **Step 1: Write the synthetic data**

`tests/sample.py`:

```python
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


def action(status, due=None, completed=None):
    return {"actionStatus": status, "dueDate": due, "completedDate": completed,
            "assignee": FAKE_NAME, "requiredAction": "Quixote to replace the guard"}


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
    action("Open", due="2026-10-02T00:00:00"),
    action("Open", due="2026-11-01T00:00:00"),
    action("Closed complete", due="2026-09-10T00:00:00", completed="2026-09-15T02:00:00"),
    action("Closed complete", due="2026-08-01T00:00:00", completed="2026-08-01T02:00:00"),
]

RAW = {"events": EVENTS, "injuries": INJURIES, "hours": HOURS,
       "actions": ACTIONS, "people": PEOPLE}
```

Worked totals for this data (the tests below assert them): Mining hours Sept 30,500, FYTD 90,500, rolling 12 months 270,500. Exploration hours Sept 3,000, FYTD 8,500, rolling 12 months 17,500. Exploration LTIFR = 1 × 1,000,000 ÷ 17,500 = 57.14.

- [ ] **Step 2: Write the failing tests**

`tests/test_metrics_table.py`:

```python
from datetime import date

import pytest

import config
import metrics
from tests import sample


@pytest.fixture
def data():
    issues = metrics.new_issues()
    events = metrics.normalise_events(sample.EVENTS, sample.INJURIES, issues)
    hours = metrics.normalise_hours(sample.HOURS, issues)
    return events, hours, issues


def row(table, label):
    return next(r for r in table if r["label"] == label)["cells"]


def test_normalise_drops_excluded_hidden_and_not_counted(data):
    events, _, _ = data
    assert sorted(e["id"] for e in events) == [1, 2, 3, 5, 6, 7, 8, 9, 12, 14]


def test_unmapped_workgroup_is_reported_not_silently_dropped(data):
    _, _, issues = data
    assert issues["unmapped"] == {"Shutdown Crew"}


def test_blank_workgroup_is_reported():
    issues = metrics.new_issues()
    events = metrics.normalise_events(
        [sample.event(1, "2026-09-01", None, "Near Miss")], [], issues)
    assert events == []
    assert issues["unmapped"] == {"(no workgroup)"}


def test_unmapped_workgroup_with_hours_is_reported():
    issues = metrics.new_issues()
    hours = metrics.normalise_hours(
        [sample.hours("Shutdown Crew", 2026, 9, 120.0), sample.hours("New Idle Group", 2026, 9, 0.0)],
        issues)
    assert hours == {}
    assert issues["unmapped"] == {"Shutdown Crew"}


def test_undated_event_is_counted_as_an_issue():
    issues = metrics.new_issues()
    bad = sample.event(1, "2026-09-01", "CPO - Ozland", "Near Miss")
    bad["eventDateTime"] = None
    assert metrics.normalise_events([bad], [], issues) == []
    assert issues["undated"] == 1


def test_event_date_falls_back_to_dd_mm_yyyy_field():
    ev = sample.event(1, "2026-09-01", "CPO - Ozland", "Near Miss")
    ev["eventDateTime"], ev["eventDate"] = None, "28-09-2026"
    events = metrics.normalise_events([ev], [], metrics.new_issues())
    assert events[0]["day"] == date(2026, 9, 28)


def test_injury_type_wins_over_sub_type(data):
    events, _, _ = data
    by_id = {e["id"]: e for e in events}
    assert by_id[3]["injury_class"] == "LTI"
    assert by_id[2]["injury_class"] == "FAI"
    assert by_id[12]["injury_class"] == "NT"
    assert by_id[5]["injury_class"] is None


def test_injury_type_can_come_from_the_injury_list():
    issues = metrics.new_issues()
    ev = sample.event(1, "2026-09-01", "CPO - Ozland", "Injury", "No Treatment Required", "")
    events = metrics.normalise_events(
        [ev], [sample.injury(1, injuryType="MTI (Medical Treatment Injury)")], issues)
    assert events[0]["injury_class"] == "MTI"


def test_hours_by_bucket_and_month(data):
    _, hours, _ = data
    assert hours[(config.MINING, (2026, 9))] == 30500.0
    assert hours[(config.EXPLORATION, (2026, 9))] == 3000.0
    assert metrics.hours_sum(hours, config.MINING, {(2026, 7), (2026, 8), (2026, 9)}) == 90500.0


def test_rate_and_formatting():
    assert metrics.rate(1, 17500.0) == pytest.approx(57.142857)
    assert metrics.rate(0, 1000.0) == 0.0
    assert metrics.rate(3, 0) is None
    assert metrics.fmt_rate(57.142857) == "57.14"
    assert metrics.fmt_rate(0.0) == "0.00"
    assert metrics.fmt_rate(None) == "NA"
    assert metrics.fmt_count(0) == "–"
    assert metrics.fmt_count(38826) == "38,826"


def test_frequency_rates_use_rolling_12_months(data):
    events, hours, _ = data
    trifr, ltifr = metrics.frequency_rates(events, hours, config.EXPLORATION, sample.MONTH)
    assert trifr == pytest.approx(57.142857) and ltifr == pytest.approx(57.142857)
    assert metrics.frequency_rates(events, hours, config.MINING, sample.MONTH) == (0.0, 0.0)


def test_head_count_is_nmg_employees_at_month_end():
    as_at = date(2026, 9, 30)
    assert metrics.head_count(sample.PEOPLE, config.MINING, as_at) == 2
    assert metrics.head_count(sample.PEOPLE, config.EXPLORATION, as_at) == 1


def test_head_count_boundaries():
    as_at = date(2026, 9, 30)
    starts_on_the_day = [sample.person("CPO - Geology", commenced="2026-09-30T00:00:00")]
    ceases_on_the_day = [sample.person("CPO - Geology", ceased="2026-09-30T00:00:00")]
    ceases_next_day = [sample.person("CPO - Geology", ceased="2026-10-01T00:00:00")]
    assert metrics.head_count(starts_on_the_day, config.MINING, as_at) == 1
    assert metrics.head_count(ceases_on_the_day, config.MINING, as_at) == 0
    assert metrics.head_count(ceases_next_day, config.MINING, as_at) == 1


def test_table_for_september_2026(data):
    events, hours, _ = data
    table = metrics.build_table(events, hours, sample.PEOPLE, sample.MONTH)
    assert row(table, "Lost Time Injury") == ["–", "–", "–", "1"]
    assert row(table, "Restricted Work Injury") == ["–", "–", "–", "–"]
    assert row(table, "First Aid Injury") == ["2", "2", "–", "–"]
    assert row(table, "No Treatment Injury") == ["–", "–", "–", "–"]   # June is last FY
    assert row(table, "Total Injuries") == ["2", "2", "–", "1"]
    assert row(table, "Near Miss") == ["2", "2", "–", "–"]
    assert row(table, "Lost Workdays") == ["–", "–", "–", "open"]
    assert row(table, "Lost Time Injury Freq Rate (LTIFR)") == ["NA", "0.00", "NA", "57.14"]
    assert row(table, "Total Recordable Injury Freq Rate (TRIFR)") == ["NA", "0.00", "NA", "57.14"]
    assert row(table, "Environmental Incidents") == ["–", "–", "–", "–"]
    assert row(table, "Property Damage / Loss") == ["1", "1", "–", "–"]
    assert row(table, "Security Incident / Violence") == ["–", "1", "–", "1"]
    assert row(table, "Misfire") == ["1", "1", "–", "–"]
    assert row(table, "NMG Head Count") == ["2", "NA", "1", "NA"]
    assert row(table, "Total Person Hours Worked") == ["30,500", "90,500", "3,000", "8,500"]


def test_table_bold_rows_and_order(data):
    events, hours, _ = data
    table = metrics.build_table(events, hours, sample.PEOPLE, sample.MONTH)
    labels = [r["label"] for r in table]
    assert labels[:6] == ["Lost Time Injury", "Restricted Work Injury", "Medically Treated Injury",
                          "First Aid Injury", "No Treatment Injury", "Total Injuries"]
    assert labels[-2:] == ["NMG Head Count", "Total Person Hours Worked"]
    assert [r["label"] for r in table if r["bold"]] == ["Total Injuries", "Total Person Hours Worked"]
    assert "Unclassified injury" not in labels


def test_new_event_type_and_unclassified_injury_get_their_own_rows():
    issues = metrics.new_issues()
    events = metrics.normalise_events([
        sample.event(1, "2026-09-02", "CPO - Ozland", "Fire & <Explosion>"),
        sample.event(2, "2026-09-03", "CPO - Ozland", "Injury", "", ""),
    ], [], issues)
    table = metrics.build_table(events, {}, [], sample.MONTH)
    assert row(table, "Fire & <Explosion>") == ["1", "1", "–", "–"]
    assert row(table, "Unclassified injury") == ["1", "1", "–", "–"]
    assert row(table, "Total Injuries") == ["1", "1", "–", "–"]


def test_lost_workdays_with_a_return_date():
    issues = metrics.new_issues()
    ev = sample.event(1, "2026-09-10", "CPO - Ozland", "Injury", "Lost Time Injury", "")
    events = metrics.normalise_events(
        [ev], [sample.injury(1, returnWorkDate="2026-09-17T00:00:00")], issues)
    table = metrics.build_table(events, {}, [], sample.MONTH)
    assert row(table, "Lost Workdays") == ["7", "7", "–", "–"]


def test_empty_data_renders_dashes_and_na_without_dividing_by_zero():
    table = metrics.build_table([], {}, [], sample.MONTH)
    assert row(table, "Total Injuries") == ["–", "–", "–", "–"]
    assert row(table, "Lost Time Injury Freq Rate (LTIFR)") == ["NA", "NA", "NA", "NA"]
    assert row(table, "Total Person Hours Worked") == ["–", "–", "–", "–"]
    assert row(table, "NMG Head Count") == ["–", "NA", "–", "NA"]
```

- [ ] **Step 3: Run to verify failure**

Run: `python -m pytest tests/test_metrics_table.py -q`
Expected: `ModuleNotFoundError: No module named 'metrics'`

- [ ] **Step 4: Write `metrics.py`**

```python
"""Raw PeopleTray lists in, one report dict out. Pure functions, no I/O."""
from collections import Counter

import config
from periods import (add_months, fy_start, long_label, month_end, month_range, parse_day,
                     rolling_12, short_label)

_COUNTED_CLASSES = tuple(code for code, _ in config.INJURY_CLASSES)
LTIFR_ROW = "Lost Time Injury Freq Rate (LTIFR)"
TRIFR_ROW = "Total Recordable Injury Freq Rate (TRIFR)"


def new_issues():
    """Things left out of the figures that a person needs to hear about."""
    return {"unmapped": set(), "undated": 0}


def _text(value):
    return (value or "").strip()


def normalise_events(events, injuries, issues):
    detail_by_id = {}
    for detail in injuries:
        detail_by_id.setdefault(detail.get("eventId"), detail)
    out = []
    for ev in events:
        which = config.bucket(ev.get("workGroup"))
        if which == config.EXCLUDED:
            continue
        if which == config.UNMAPPED:
            issues["unmapped"].add(_text(ev.get("workGroup")) or "(no workgroup)")
            continue
        day = parse_day(ev.get("eventDateTime")) or parse_day(ev.get("eventDate"))
        if day is None:
            issues["undated"] += 1
            continue
        detail = detail_by_id.get(ev.get("eventId"), {})
        injury_class = None
        if _text(ev.get("eventType")) == config.INJURY_TYPE:
            injury_class = config.classify_injury(
                _text(ev.get("injuryType")) or detail.get("injuryType"),
                _text(ev.get("eventSubType")) or detail.get("eventSubTypeName"))
            if injury_class in config.NOT_COUNTED:
                continue
            row = injury_class
        else:
            row = config.event_row(ev.get("eventType"))
            if row is None:
                continue
        out.append({
            "id": ev.get("eventId"), "day": day, "ym": (day.year, day.month),
            "bucket": which, "row": row, "injury_class": injury_class,
            "open": "open" in _text(ev.get("eventStatus")).lower(),
            "return_day": parse_day(detail.get("returnWorkDate")),
            "body": _text(detail.get("injuryBodyLocation")),
            "nature": _text(detail.get("injuryNature")),
            "mechanism": _text(detail.get("injuryMechanism")),
        })
    return out


def normalise_hours(rows, issues):
    hours = {}
    for r in rows:
        value = float(r.get("exposureHours") or 0)
        which = config.bucket(r.get("groupName"))
        if which == config.UNMAPPED and value:
            issues["unmapped"].add(_text(r.get("groupName")) or "(no workgroup)")
        if which not in config.BUCKETS:
            continue
        key = (which, (int(r["year"]), int(r["month"])))
        hours[key] = hours.get(key, 0.0) + value
    return hours


def _in(events, bucket, months):
    return [e for e in events if e["bucket"] == bucket and e["ym"] in months]


def count(events, bucket, months, row):
    return sum(1 for e in _in(events, bucket, months) if e["row"] == row)


def hours_sum(hours, bucket, months):
    return sum(hours.get((bucket, m), 0.0) for m in months)


def rate(n, hours):
    return n * 1_000_000 / hours if hours else None


def fmt_count(n):
    return f"{n:,}" if n else "–"


def fmt_rate(r):
    return "NA" if r is None else f"{r:.2f}"


def frequency_rates(events, hours, bucket, month):
    window = set(rolling_12(month))
    in_window = _in(events, bucket, window)
    worked = hours_sum(hours, bucket, window)
    recordable = sum(1 for e in in_window if e["injury_class"] in config.RECORDABLE)
    lost_time = sum(1 for e in in_window if e["injury_class"] == "LTI")
    return rate(recordable, worked), rate(lost_time, worked)


def head_count(people, bucket, as_at):
    """NMG's own employees, no contractors, employed on the as_at day."""
    total = 0
    for p in people:
        if _text(p.get("employer")) != config.NMG_EMPLOYER:
            continue
        if _text(p.get("emplpyeeType")) == "Contractor":     # PeopleTray's spelling
            continue
        if config.bucket(p.get("workGroup")) != bucket:
            continue
        commenced, ceased = parse_day(p.get("dateCommenced")), parse_day(p.get("dateCeased"))
        if commenced and commenced > as_at:
            continue
        if ceased and ceased <= as_at:
            continue
        total += 1
    return total


def _lost_workdays(events, bucket, months):
    days, still_off = 0, False
    for e in _in(events, bucket, months):
        if e["injury_class"] != "LTI":
            continue
        if e["return_day"] is None:
            still_off = True
        else:
            days += max((e["return_day"] - e["day"]).days, 0)
    if still_off:
        return f"{days:,} + open" if days else "open"
    return fmt_count(days)


def build_table(events, hours, people, month):
    periods = ({month}, set(month_range(fy_start(month), month)))

    def cells(value):
        """value(bucket, months, is_fytd) for Mining month, Mining FYTD, Exploration month, Exploration FYTD."""
        return [value(b, months, i == 1) for b in config.BUCKETS for i, months in enumerate(periods)]

    def counted(row):
        return cells(lambda b, months, _: fmt_count(count(events, b, months, row)))

    def line(label, values, bold=False):
        return {"label": label, "cells": values, "bold": bold}

    def rate_row(index):
        return cells(lambda b, _, fytd:
                     fmt_rate(frequency_rates(events, hours, b, month)[index]) if fytd else "NA")

    rows_present = {e["row"] for e in events}
    table = [line(label, counted(code)) for code, label in config.INJURY_CLASSES]
    if config.UNCLASSIFIED in rows_present:
        table.append(line(config.UNCLASSIFIED, counted(config.UNCLASSIFIED)))
    table.append(line("Total Injuries", cells(lambda b, months, _: fmt_count(
        sum(1 for e in _in(events, b, months) if e["injury_class"]))), bold=True))
    table.append(line(config.NEAR_MISS_ROW, counted(config.NEAR_MISS_ROW)))
    table.append(line("Lost Workdays", cells(lambda b, months, _: _lost_workdays(events, b, months))))
    table.append(line(LTIFR_ROW, rate_row(1)))
    table.append(line(TRIFR_ROW, rate_row(0)))

    known = set(_COUNTED_CLASSES) | {config.UNCLASSIFIED, config.NEAR_MISS_ROW} | set(config.FIXED_EVENT_ROWS)
    for label in list(config.FIXED_EVENT_ROWS) + sorted(rows_present - known):
        table.append(line(label, counted(label)))

    as_at = month_end(month)
    table.append(line("NMG Head Count", cells(
        lambda b, _, fytd: "NA" if fytd else fmt_count(head_count(people, b, as_at)))))
    table.append(line("Total Person Hours Worked", cells(
        lambda b, months, _: fmt_count(round(hours_sum(hours, b, months)))), bold=True))
    return table
```

- [ ] **Step 5: Run to verify pass**

Run: `python -m pytest tests/test_metrics_table.py -q`
Expected: `18 passed`

- [ ] **Step 6: Commit**

```bash
git add metrics.py tests/sample.py tests/test_metrics_table.py
git commit -m "Add event normalising, the event table and frequency rates"
```

---

### Task 4: `metrics.py` — KPIs, trends, injury analysis, status and `build_report`

**Files:**
- Modify: `metrics.py` (append)
- Create: `tests/test_metrics_report.py`

**Interfaces:**
- Consumes: everything Task 3 produced.
- Produces: `build_report(raw: dict, today: date, generated: str) -> dict` with exactly these keys:
  - `"month_label"`: `"September 2026"`
  - `"generated"`: the string passed in
  - `"kpis"`: `{bucket: [(label, value_str), ...]}` — five tiles per bucket, in this order: `TRIFR`, `LTIFR`, `Injuries in month`, `Days since last LTI`, `Person hours in month`
  - `"table"`: from `build_table`
  - `"trend"`: `{"labels": [12 str], "trifr": {bucket: [12 float|None]}, "ltifr": {bucket: [12 float|None]}}`
  - `"event_trend"`: `{"labels": [12 str], "series": [(group_name, [12 int]), ...]}` — one entry per `config.TREND_GROUPS`, same order
  - `"injury_analysis"`: `[(title, [(label, count), ...]), ...]` — titles `Body location`, `Nature of injury`, `Mechanism of injury`
  - `"status"`: `{"events_open", "events_closed", "actions_open", "actions_overdue", "actions_closed_month"}` — ints
  - `"unmapped"`: sorted list of str; `"undated"`: int

- [ ] **Step 1: Write the failing tests**

`tests/test_metrics_report.py`:

```python
import pytest

import config
import metrics
from tests import sample


@pytest.fixture(scope="module")
def report():
    return metrics.build_report(sample.RAW, sample.TODAY, "11 Oct 2026, 18:30 AWST")


def test_report_keys(report):
    assert set(report) == {"month_label", "generated", "kpis", "table", "trend", "event_trend",
                           "injury_analysis", "status", "unmapped", "undated"}
    assert report["month_label"] == "September 2026"
    assert report["generated"] == "11 Oct 2026, 18:30 AWST"
    assert report["unmapped"] == ["Shutdown Crew"]
    assert report["undated"] == 0


def test_kpis(report):
    assert report["kpis"][config.MINING] == [
        ("TRIFR", "0.00"), ("LTIFR", "0.00"), ("Injuries in month", "2"),
        ("Days since last LTI", "None recorded"), ("Person hours in month", "30,500")]
    assert report["kpis"][config.EXPLORATION] == [
        ("TRIFR", "57.14"), ("LTIFR", "57.14"), ("Injuries in month", "–"),
        ("Days since last LTI", "58"), ("Person hours in month", "3,000")]


def test_trend_has_12_labelled_points(report):
    trend = report["trend"]
    assert len(trend["labels"]) == 12
    assert trend["labels"][0] == "Oct 25" and trend["labels"][-1] == "Sep 26"
    assert trend["trifr"][config.EXPLORATION][-1] == pytest.approx(57.142857)
    # August point: one LTI over the 12,500 Exploration hours from Oct 25 to Aug 26
    assert trend["ltifr"][config.EXPLORATION][-2] == pytest.approx(80.0)
    assert trend["ltifr"][config.EXPLORATION][-3] == 0.0
    assert trend["trifr"][config.MINING] == [0.0] * 12


def test_trend_point_with_no_hours_is_none():
    raw = dict(sample.RAW, hours=[sample.hours("CPO - Ozland", 2026, 9, 1000.0)])
    trend = metrics.build_report(raw, sample.TODAY, "x")["trend"]
    assert trend["trifr"][config.EXPLORATION] == [None] * 12
    assert trend["trifr"][config.MINING][-1] == 0.0
    assert trend["trifr"][config.MINING][0] is None


def test_event_trend_groups(report):
    trend = report["event_trend"]
    assert trend["labels"] == report["trend"]["labels"]
    assert [name for name, _ in trend["series"]] == list(config.TREND_GROUPS)
    september = {name: values[-1] for name, values in trend["series"]}
    assert september == {"Injury": 2, "Near Miss": 2, "Property Damage / Loss": 1,
                         "Procedural Compliance": 0, "Production Loss": 0, "Other": 1}
    august = {name: values[-2] for name, values in trend["series"]}
    assert august["Injury"] == 1 and august["Other"] == 1      # the LTI, and the Security event


def test_injury_analysis(report):
    analysis = dict(report["injury_analysis"])
    assert list(analysis) == ["Body location", "Nature of injury", "Mechanism of injury"]
    assert analysis["Body location"] == [("Not recorded", 2), ("Back", 1), ("Hands and fingers", 1)]
    assert analysis["Nature of injury"] == [("Not recorded", 3), ("Superficial injury", 1)]


def test_injury_analysis_groups_the_long_tail():
    events = [sample.event(i, "2026-09-01", "CPO - Ozland", "Injury", "First Aid Injury")
              for i in range(1, 11)]
    injuries = [sample.injury(i, injuryBodyLocation=f"Part {i:02d}") for i in range(1, 11)]
    raw = {"events": events, "injuries": injuries, "hours": [], "actions": [], "people": []}
    body = dict(metrics.build_report(raw, sample.TODAY, "x")["injury_analysis"])["Body location"]
    assert len(body) == 9
    assert body[-1] == ("Other", 2)


def test_status(report):
    assert report["status"] == {"events_open": 1, "events_closed": 9, "actions_open": 2,
                                "actions_overdue": 1, "actions_closed_month": 1}


def test_empty_feeds_build_a_report():
    raw = {"events": [], "injuries": [], "hours": [], "actions": [], "people": []}
    report = metrics.build_report(raw, sample.TODAY, "x")
    assert report["kpis"][config.MINING][0] == ("TRIFR", "NA")
    assert report["injury_analysis"][0] == ("Body location", [])
    assert report["status"]["events_open"] == 0
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_metrics_report.py -q`
Expected: `AttributeError: module 'metrics' has no attribute 'build_report'`

- [ ] **Step 3: Append to `metrics.py`**

```python
def build_kpis(events, hours, month, today):
    kpis = {}
    for b in config.BUCKETS:
        trifr, ltifr = frequency_rates(events, hours, b, month)
        lti_days = [e["day"] for e in events if e["bucket"] == b and e["injury_class"] == "LTI"]
        since = str((today - max(lti_days)).days) if lti_days else "None recorded"
        injuries = sum(1 for e in _in(events, b, {month}) if e["injury_class"])
        kpis[b] = [
            ("TRIFR", fmt_rate(trifr)),
            ("LTIFR", fmt_rate(ltifr)),
            ("Injuries in month", fmt_count(injuries)),
            ("Days since last LTI", since),
            ("Person hours in month", fmt_count(round(hours_sum(hours, b, {month})))),
        ]
    return kpis


def build_trend(events, hours, month):
    points = rolling_12(month)
    trend = {"labels": [short_label(p) for p in points],
             "trifr": {b: [] for b in config.BUCKETS},
             "ltifr": {b: [] for b in config.BUCKETS}}
    for point in points:
        for b in config.BUCKETS:
            trifr, ltifr = frequency_rates(events, hours, b, point)
            trend["trifr"][b].append(trifr)
            trend["ltifr"][b].append(ltifr)
    return trend


def _trend_group(event):
    if event["injury_class"]:
        return "Injury"
    return event["row"] if event["row"] in config.TREND_GROUPS else "Other"


def build_event_trend(events, month):
    points = rolling_12(month)
    tally = Counter((_trend_group(e), e["ym"]) for e in events)
    return {"labels": [short_label(p) for p in points],
            "series": [(group, [tally[(group, p)] for p in points]) for group in config.TREND_GROUPS]}


def _breakdown(values, keep=8):
    ranked = sorted(Counter(v or "Not recorded" for v in values).items(),
                    key=lambda item: (-item[1], item[0]))
    if len(ranked) > keep + 1:
        ranked = ranked[:keep] + [("Other", sum(n for _, n in ranked[keep:]))]
    return ranked


def build_injury_analysis(events, month):
    window = set(rolling_12(month))
    injured = [e for e in events if e["injury_class"] in _COUNTED_CLASSES and e["ym"] in window]
    return [("Body location", _breakdown([e["body"] for e in injured])),
            ("Nature of injury", _breakdown([e["nature"] for e in injured])),
            ("Mechanism of injury", _breakdown([e["mechanism"] for e in injured]))]


def build_status(events, actions, month, today):
    window = set(rolling_12(month))
    recent = [e for e in events if e["ym"] in window]
    status = {"events_open": sum(1 for e in recent if e["open"]),
              "events_closed": sum(1 for e in recent if not e["open"]),
              "actions_open": 0, "actions_overdue": 0, "actions_closed_month": 0}
    for a in actions:
        state = _text(a.get("actionStatus")).lower()
        if state == "open":
            status["actions_open"] += 1
            due = parse_day(a.get("dueDate"))
            if due and due < today:
                status["actions_overdue"] += 1
        elif state.startswith("closed"):
            done = parse_day(a.get("completedDate"))
            if done and (done.year, done.month) == month:
                status["actions_closed_month"] += 1
    return status


def build_report(raw, today, generated):
    month = add_months((today.year, today.month), -1)
    issues = new_issues()
    events = normalise_events(raw["events"], raw["injuries"], issues)
    hours = normalise_hours(raw["hours"], issues)
    return {
        "month_label": long_label(month),
        "generated": generated,
        "kpis": build_kpis(events, hours, month, today),
        "table": build_table(events, hours, raw["people"], month),
        "trend": build_trend(events, hours, month),
        "event_trend": build_event_trend(events, month),
        "injury_analysis": build_injury_analysis(events, month),
        "status": build_status(events, raw["actions"], month, today),
        "unmapped": sorted(issues["unmapped"]),
        "undated": issues["undated"],
    }
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest -q`
Expected: all tests pass (9 new in `test_metrics_report.py`)

- [ ] **Step 5: Commit**

```bash
git add metrics.py tests/test_metrics_report.py
git commit -m "Add KPI, trend, injury analysis and status metrics"
```

---

### Task 5: `peopletray.py` and `fetch.py`

**Files:**
- Create: `peopletray.py`, `fetch.py`, `tests/test_fetch.py`

**Interfaces:**
- Consumes: `periods.reporting_month`, `periods.add_months`
- Produces: `peopletray.load_key(env=os.environ, key_file=KEY_FILE) -> str`; `peopletray.get(path, params=None, opener=urllib.request.urlopen, sleep=time.sleep) -> object` (parsed JSON; raises `RuntimeError` after 4 failed attempts); `fetch.fetch_all(today: date, get=peopletray.get) -> dict` with keys `events, injuries, hours, actions, people`, each a list (raises `ValueError` if any is not a list).

- [ ] **Step 1: Write the failing tests**

`tests/test_fetch.py`:

```python
import io
import json
from datetime import date

import pytest

import fetch
import peopletray


def test_key_comes_from_env_first(tmp_path):
    key_file = tmp_path / "key.txt"
    key_file.write_text("label\nfile-key\n", encoding="utf-8")
    assert peopletray.load_key({"PT_API_KEY": " env-key "}, key_file) == "env-key"


def test_key_falls_back_to_line_2_of_the_file(tmp_path):
    key_file = tmp_path / "key.txt"
    key_file.write_text("﻿PT API Key for NMG
file-key
", encoding="utf-8")
    assert peopletray.load_key({}, key_file) == "file-key"


def test_missing_key_is_an_error(tmp_path):
    with pytest.raises(RuntimeError, match="PT_API_KEY"):
        peopletray.load_key({}, tmp_path / "absent.txt")


def test_get_retries_then_succeeds(monkeypatch):
    monkeypatch.setenv("PT_API_KEY", "k")
    calls, naps = [], []

    def opener(request, timeout):
        calls.append(request)
        if len(calls) < 3:
            raise OSError("connection reset")
        return io.BytesIO(json.dumps([{"a": 1}]).encode())

    result = peopletray.get("/api/v2/powerbi/events", {"fromDate": "2026-01-01"},
                            opener=opener, sleep=naps.append)
    assert result == [{"a": 1}]
    assert len(calls) == 3 and len(naps) == 2
    assert calls[0].full_url.endswith("/api/v2/powerbi/events?fromDate=2026-01-01")
    assert calls[0].get_header("X-api-key") == "k"


def test_get_gives_up_after_4_attempts(monkeypatch):
    monkeypatch.setenv("PT_API_KEY", "k")
    calls = []

    def opener(request, timeout):
        calls.append(request)
        raise OSError("down")

    with pytest.raises(RuntimeError, match="/api/v2/powerbi/people"):
        peopletray.get("/api/v2/powerbi/people", opener=opener, sleep=lambda s: None)
    assert len(calls) == 4


def test_fetch_all_window_and_keys():
    seen = []

    def fake_get(path, params=None):
        seen.append((path, params))
        return [{"path": path}]

    raw = fetch.fetch_all(date(2026, 10, 11), get=fake_get)
    assert set(raw) == {"events", "injuries", "hours", "actions", "people"}
    window = {"fromDate": "2024-11-01", "toDate": "2026-10-12"}
    assert ("/api/v2/powerbi/events", window) in seen
    assert ("/api/v2/powerbi/eventinjurylist", window) in seen
    assert ("/api/v2/powerbi/exposurehours", window) in seen
    assert ("/api/v2/powerbi/actions", window) in seen
    assert ("/api/v2/powerbi/people", None) in seen


def test_fetch_all_rejects_a_non_list_response():
    def fake_get(path, params=None):
        return {"message": "An error has occurred."} if path.endswith("exposurehours") else []

    with pytest.raises(ValueError, match="hours"):
        fetch.fetch_all(date(2026, 10, 11), get=fake_get)
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_fetch.py -q`
Expected: `ModuleNotFoundError: No module named 'fetch'`

- [ ] **Step 3: Write `peopletray.py`**

```python
"""Authenticated GET against the PeopleTray API, with retries."""
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE_URL = "https://api-peopletray.azurewebsites.net"
# Shared with the other NMG projects; the key is on line 2, under a label line.
KEY_FILE = Path(r"C:\claude\PeopleTray DAS\reference\PT API Key for NMG.txt")
ATTEMPTS = 4


def load_key(env=os.environ, key_file=KEY_FILE):
    key = (env.get("PT_API_KEY") or "").strip()
    if key:
        return key
    try:
        return Path(key_file).read_text(encoding="utf-8-sig").splitlines()[1].strip()
    except (OSError, IndexError):
        raise RuntimeError(f"No PeopleTray key: set PT_API_KEY or provide {key_file}") from None


def get(path, params=None, opener=urllib.request.urlopen, sleep=time.sleep):
    url = BASE_URL + path + ("?" + urllib.parse.urlencode(params) if params else "")
    request = urllib.request.Request(url, headers={"X-API-Key": load_key()})
    last_error = None
    for attempt in range(ATTEMPTS):
        if attempt:
            sleep(5 * 2 ** (attempt - 1))
        try:
            with opener(request, timeout=120) as response:
                return json.loads(response.read())
        except (OSError, ValueError) as error:    # URLError and HTTPError are OSErrors
            last_error = error
    raise RuntimeError(f"PeopleTray {path} failed after {ATTEMPTS} attempts: {last_error}")
```

- [ ] **Step 4: Write `fetch.py`**

```python
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
```

- [ ] **Step 5: Run to verify pass**

Run: `python -m pytest tests/test_fetch.py -q`
Expected: `7 passed`

- [ ] **Step 6: Check against the live API**

Run:

```bash
python -c "import fetch, periods; raw = fetch.fetch_all(periods.today_perth()); print({k: len(v) for k, v in raw.items()})"
```

Expected: five non-zero counts, roughly `{'events': 138+, 'injuries': 130+, 'hours': 250+, 'actions': 60+, 'people': 372}`. If any is 0 or the call raises, stop and investigate before continuing.

- [ ] **Step 7: Commit**

```bash
git add peopletray.py fetch.py tests/test_fetch.py
git commit -m "Add PeopleTray client and fetch window"
```

---

### Task 6: `render.py`

**Files:**
- Create: `render.py`, `tests/test_render.py`, `assets/nmg_logo.png`

**Interfaces:**
- Consumes: the `report` dict exactly as Task 4 defines it; `config.SERIES_COLOURS`, `config.TREND_COLOURS`, `config.BUCKETS`, colour constants.
- Produces: `render.render(report: dict, logo_b64: str | None = None) -> str` — a complete HTML document. Section elements carry ids `kpis`, `event-table`, `rate-trends`, `event-trend`, `injury-analysis`, `status`; the unmapped notice has id `notice`.

- [ ] **Step 1: Make the logo asset**

The source logo is 590 KB, too heavy to inline. Downscale it once to 360 px wide (PowerShell, no extra installs):

```powershell
New-Item -ItemType Directory -Force "C:\claude\NMG OHS Dashboard\assets" | Out-Null
Add-Type -AssemblyName System.Drawing
$src = [System.Drawing.Image]::FromFile("F:\NMG\04_NMG - Documents (Produced by ESA)\Landscape NMG logo colour transparent background.png")
$w = 360; $h = [int]($src.Height * $w / $src.Width)
$bmp = New-Object System.Drawing.Bitmap $w, $h
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.InterpolationMode = 'HighQualityBicubic'
$g.DrawImage($src, 0, 0, $w, $h)
$bmp.Save("C:\claude\NMG OHS Dashboard\assets\nmg_logo.png", [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $bmp.Dispose(); $src.Dispose()
(Get-Item "C:\claude\NMG OHS Dashboard\assets\nmg_logo.png").Length
```

Expected: a size under 60,000 bytes. Open the file with the Read tool and confirm it shows the NMG landscape logo on a transparent background with no large empty margin.

- [ ] **Step 2: Write the failing tests**

`tests/test_render.py`:

```python
import re

import pytest

import config
import metrics
import render
from tests import sample


@pytest.fixture(scope="module")
def report():
    return metrics.build_report(sample.RAW, sample.TODAY, "11 Oct 2026, 18:30 AWST")


@pytest.fixture(scope="module")
def page(report):
    return render.render(report, logo_b64="AAAA")


def test_is_a_complete_self_contained_document(page):
    assert page.startswith("<!doctype html>")
    assert page.rstrip().endswith("</html>")
    assert "<script" not in page
    assert not re.search(r'(src|href)="https?://', page)
    assert 'src="data:image/png;base64,AAAA"' in page


def test_every_section_is_present(page):
    for section in ("kpis", "event-table", "rate-trends", "event-trend", "injury-analysis", "status"):
        assert f'id="{section}"' in page


def test_header_shows_month_and_timestamp(page):
    assert "September 2026" in page
    assert "11 Oct 2026, 18:30 AWST" in page


def test_table_rows_and_cells(page):
    assert "<th>Mining</th>" not in page          # bucket headings span two columns
    assert 'colspan="2">Mining<' in page and 'colspan="2">Exploration<' in page
    assert re.search(r"<th[^>]*>Total Person Hours Worked</th><td>30,500</td><td>90,500</td>"
                     r"<td>3,000</td><td>8,500</td>", page)
    assert re.search(r"<th[^>]*>Lost Time Injury Freq Rate \(LTIFR\)</th><td>NA</td><td>0.00</td>"
                     r"<td>NA</td><td>57.14</td>", page)


def test_kpi_tiles(page):
    assert page.count('class="tile"') == 10
    assert "Days since last LTI" in page and ">58<" in page


def test_charts_are_inline_svg_with_month_labels(page):
    assert page.count("<svg") == 3                # TRIFR, LTIFR, event trend
    assert ">Oct 25<" in page and ">Sep 26<" in page
    assert config.NAVY in page and config.GOLD in page
    assert "NaN" not in page and "None" not in page


def test_unmapped_notice_names_the_workgroup(page):
    assert 'id="notice"' in page
    assert "Shutdown Crew" in page


def test_no_notice_when_nothing_is_unmapped(report):
    clean = dict(report, unmapped=[], undated=0)
    assert 'id="notice"' not in render.render(clean)


def test_undated_events_are_mentioned(report):
    page = render.render(dict(report, unmapped=[], undated=2))
    assert 'id="notice"' in page and "2 events" in page


def test_no_personal_or_descriptive_data_reaches_the_page(page):
    for forbidden in ("Zebedee", "Quixote", "slipped", "Workshop bay", "replace the guard"):
        assert forbidden not in page


def test_peopletray_text_is_escaped():
    events = [sample.event(1, "2026-09-02", "CPO - Ozland", "Fire & <Explosion>")]
    raw = {"events": events, "injuries": [], "hours": [], "actions": [], "people": []}
    page = render.render(metrics.build_report(raw, sample.TODAY, "x"))
    assert "Fire &amp; &lt;Explosion&gt;" in page
    assert "<Explosion>" not in page


def test_empty_report_renders_without_a_logo():
    raw = {"events": [], "injuries": [], "hours": [], "actions": [], "people": []}
    page = render.render(metrics.build_report(raw, sample.TODAY, "x"))
    assert 'class="wordmark"' in page
    assert "No injuries recorded in the last 12 months" in page
    assert page.count("<svg") == 3


def test_nice_axis_maximum():
    assert render.nice_max(0) == 5
    assert render.nice_max(4.2) == 5
    assert render.nice_max(22.52) == 25
    assert render.nice_max(57.14) == 100
    assert render.nice_max(7) == 10
    assert render.nice_max(130) == 250
```

- [ ] **Step 3: Run to verify failure**

Run: `python -m pytest tests/test_render.py -q`
Expected: `ModuleNotFoundError: No module named 'render'`

- [ ] **Step 4: Write `render.py`**

```python
"""The report dict as one self-contained HTML page. No data logic here."""
from html import escape

import config

CSS = """
:root{--navy:#083045;--river:#55848A;--gold:#927128;--pale-gold:#B19045;--sand:#F1DCAA;
--sand-tint:#F8EED5;--grey:#DBDBD3;--grey-tint:#EDEDE9;--river-tint:#AAC2C5;--ink:#333334;--muted:#6b6b6c}
*{box-sizing:border-box}
body{margin:0;background:var(--grey-tint);color:var(--ink);
font-family:"Proxima Nova",Aptos,"Segoe UI",system-ui,sans-serif;font-size:15px;line-height:1.45}
.wrap{max-width:1180px;margin:0 auto;padding:0 16px 32px}
header{background:#fff;border-bottom:4px solid var(--gold)}
header .wrap{display:flex;align-items:center;gap:20px;flex-wrap:wrap;padding-top:14px;padding-bottom:14px}
header img{height:54px;width:auto}
.wordmark{font-weight:900;font-size:34px;color:var(--navy);letter-spacing:1px}
header h1{margin:0;font-size:24px;font-weight:900;color:var(--navy);line-height:1.15}
header p{margin:2px 0 0;color:var(--muted);font-size:13px}
header .month{margin-left:auto;text-align:right}
header .month strong{display:block;font-size:20px;color:var(--navy)}
section{background:#fff;border-radius:6px;margin-top:18px;overflow:hidden;
box-shadow:0 1px 2px rgba(8,48,69,.12)}
section>h2{margin:0;padding:9px 16px;background:var(--navy);color:#fff;font-size:14px;
font-weight:700;letter-spacing:.06em;text-transform:uppercase}
.pad{padding:16px}
.note{color:var(--muted);font-size:13px;margin:10px 0 0}
#notice{background:var(--sand-tint);border-left:5px solid var(--pale-gold);padding:12px 16px;
margin-top:18px;border-radius:4px}
.bucket{display:flex;align-items:stretch;gap:10px;flex-wrap:wrap;margin-bottom:10px}
.bucket:last-child{margin-bottom:0}
.bucket h3{flex:0 0 118px;margin:0;display:flex;align-items:center;justify-content:center;
color:#fff;border-radius:4px;font-size:15px;text-transform:uppercase;letter-spacing:.05em}
.tile{flex:1 1 150px;background:var(--grey-tint);border-radius:4px;padding:10px 12px;
border-top:3px solid var(--river)}
.tile b{display:block;font-size:26px;font-weight:900;color:var(--navy);line-height:1.2}
.tile span{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;min-width:560px}
th,td{padding:7px 10px;border-bottom:1px solid var(--grey);text-align:center}
thead th{color:#fff;font-weight:700}
thead tr:first-child th{background:var(--river-tint);color:var(--navy);font-size:16px;
letter-spacing:.05em;text-transform:uppercase}
thead tr:last-child th{background:#8498A2}
tbody th{text-align:left;font-weight:400}
tbody tr.bold th,tbody tr.bold td{font-weight:900;color:var(--navy);border-top:2px solid var(--river);
border-bottom:2px solid var(--river)}
tbody td{font-variant-numeric:tabular-nums}
tbody tr:nth-child(even){background:#fafaf8}
.cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:18px}
.card h3{margin:0 0 6px;font-size:16px;color:var(--navy);text-align:center}
svg{width:100%;height:auto;display:block}
svg .grid{stroke:var(--grey);stroke-width:1}
svg .tick{font-size:10px;fill:var(--muted)}
.legend{display:flex;gap:16px;justify-content:center;flex-wrap:wrap;font-size:13px;margin-top:6px}
.legend i{display:inline-block;width:14px;height:10px;margin-right:5px;border-radius:2px}
.bars{display:grid;grid-template-columns:minmax(110px,42%) 1fr 30px;gap:5px 8px;align-items:center;
font-size:13px}
.bars .track{background:var(--grey-tint);border-radius:3px;height:14px}
.bars .fill{background:var(--river);border-radius:3px;height:14px}
.bars .n{text-align:right;font-variant-numeric:tabular-nums;font-weight:700}
details{margin-top:10px;font-size:13px}
details summary{cursor:pointer;color:var(--river)}
footer{color:var(--muted);font-size:12px;margin-top:18px}
footer p{margin:4px 0}
@media(max-width:600px){header .month{margin-left:0;text-align:left}.bucket h3{flex:1 1 100%;padding:6px}
header h1{font-size:20px}}
"""

W, H, LEFT, RIGHT, TOP, BOTTOM = 560, 250, 40, 14, 14, 30


def nice_max(value):
    """Smallest of 5, 10, 25, 50, 100, 250, ... that is not below value."""
    step = 1
    while True:
        for multiple in (5, 10, 25):
            if value <= step * multiple:
                return step * multiple
        step *= 10


def _axes(labels, top):
    def y(v):
        return TOP + (H - TOP - BOTTOM) * (1 - v / top)

    parts = []
    for k in range(6):
        v = top * k / 5
        parts.append(f'<line class="grid" x1="{LEFT}" x2="{W - RIGHT}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>'
                     f'<text class="tick" x="{LEFT - 6}" y="{y(v) + 3.5:.1f}" text-anchor="end">{v:g}</text>')
    return parts, y


def _legend(items):
    return '<div class="legend">' + "".join(
        f'<span><i style="background:{colour}"></i>{escape(name)}</span>' for name, colour in items
    ) + "</div>"


def _line_chart(title, labels, series):
    values = [v for line in series.values() for v in line if v is not None]
    parts, y = _axes(labels, nice_max(max(values, default=0)))
    span = max(len(labels) - 1, 1)

    def x(i):
        return LEFT + (W - LEFT - RIGHT) * i / span

    for i, label in enumerate(labels):
        parts.append(f'<text class="tick" x="{x(i):.1f}" y="{H - 10}" text-anchor="middle">{escape(label)}</text>')
    for name, line in series.items():
        colour = config.SERIES_COLOURS[name]
        run = []
        for i, v in enumerate(list(line) + [None]):       # the trailing None flushes the last run
            if v is None:
                if len(run) > 1:
                    parts.append(f'<polyline fill="none" stroke="{colour}" stroke-width="3" '
                                 f'stroke-linejoin="round" points="{" ".join(run)}"/>')
                run = []
            else:
                run.append(f"{x(i):.1f},{y(v):.1f}")
                parts.append(f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="3" fill="{colour}"/>')
    svg = f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{escape(title)}">{"".join(parts)}</svg>'
    legend = _legend([(name, config.SERIES_COLOURS[name]) for name in series])
    return f'<div class="card"><h3>{escape(title)}</h3>{svg}{legend}</div>'


def _stacked_bars(title, labels, series):
    totals = [sum(values[i] for _, values in series) for i in range(len(labels))]
    parts, y = _axes(labels, nice_max(max(totals, default=0)))
    slot = (W - LEFT - RIGHT) / max(len(labels), 1)
    bar = slot * 0.62
    for i, label in enumerate(labels):
        centre = LEFT + slot * (i + 0.5)
        parts.append(f'<text class="tick" x="{centre:.1f}" y="{H - 10}" text-anchor="middle">{escape(label)}</text>')
        base = 0
        for (name, values), colour in zip(series, config.TREND_COLOURS):
            if values[i]:
                top_y, bottom_y = y(base + values[i]), y(base)
                parts.append(f'<rect x="{centre - bar / 2:.1f}" y="{top_y:.1f}" width="{bar:.1f}" '
                             f'height="{bottom_y - top_y:.1f}" fill="{colour}">'
                             f'<title>{escape(name)}: {values[i]}</title></rect>')
                base += values[i]
    svg = f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{escape(title)}">{"".join(parts)}</svg>'
    return svg + _legend([(name, colour) for (name, _), colour in zip(series, config.TREND_COLOURS)])


def _header(report, logo_b64):
    logo = (f'<img src="data:image/png;base64,{logo_b64}" alt="New Murchison Gold Limited">'
            if logo_b64 else '<span class="wordmark">NMG</span>')
    return (f'<header><div class="wrap">{logo}<div><h1>Health &amp; Safety Performance</h1>'
            f'<p>New Murchison Gold Limited</p></div><div class="month">'
            f'<strong>{escape(report["month_label"])}</strong>'
            f'<p>Data as at {escape(report["generated"])}</p></div></div></header>')


def _notice(report):
    lines = []
    if report["unmapped"]:
        names = ", ".join(escape(name) for name in report["unmapped"])
        lines.append(f"<strong>Unmapped workgroup:</strong> {names}. Events and hours for "
                     "these are not included in the figures below until they are assigned to "
                     "Mining or Exploration.")
    if report["undated"]:
        plural = "event has" if report["undated"] == 1 else "events have"
        lines.append(f'<strong>Undated:</strong> {report["undated"]} {plural} no date in '
                     "PeopleTray and could not be counted.")
    return f'<div id="notice">{"<br>".join(lines)}</div>' if lines else ""


def _kpis(report):
    blocks = []
    for name in config.BUCKETS:
        tiles = "".join(f'<div class="tile"><b>{escape(value)}</b><span>{escape(label)}</span></div>'
                        for label, value in report["kpis"][name])
        blocks.append(f'<div class="bucket"><h3 style="background:{config.SERIES_COLOURS[name]}">'
                      f'{escape(name)}</h3>{tiles}</div>')
    return (f'<section id="kpis"><h2>Key indicators</h2><div class="pad">{"".join(blocks)}'
            '<p class="note">TRIFR and LTIFR are rolling 12-month rates per million hours worked.</p>'
            "</div></section>")


def _table(report):
    month = escape(report["month_label"].split(" ")[0])
    heads = "".join(f'<th colspan="2">{escape(name)}</th>' for name in config.BUCKETS)
    subs = "".join(f"<th>{month}</th><th>FYTD</th>" for _ in config.BUCKETS)
    body = "".join(
        ('<tr class="bold">' if row["bold"] else "<tr>")
        + f'<th scope="row">{escape(row["label"])}</th>'
        + "".join(f"<td>{escape(cell)}</td>" for cell in row["cells"]) + "</tr>"
        for row in report["table"])
    return ('<section id="event-table"><h2>Events &mdash; month and financial year to date</h2>'
            f'<div class="scroll"><table><thead><tr><th></th>{heads}</tr>'
            f"<tr><th>Event</th>{subs}</tr></thead><tbody>{body}</tbody></table></div>"
            '<div class="pad"><p class="note">Frequency rates in the FYTD columns are rolling '
            "12-month rates. Head count is NMG employees only, at month end. FYTD runs from 1 July."
            "</p></div></section>")


def _trends(report):
    trend = report["trend"]
    charts = (_line_chart("TRIFR 12 Month Trend", trend["labels"], trend["trifr"])
              + _line_chart("LTIFR 12 Month Trend", trend["labels"], trend["ltifr"]))
    return ('<section id="rate-trends"><h2>Total recordable injury &amp; lost time injury '
            f'frequency rates</h2><div class="pad"><div class="cols">{charts}</div>'
            '<p class="note">Total Recordable Injury Frequency Rate (TRIFR) and Lost Time Injury '
            "Frequency Rate (LTIFR) are calculated over 12 months. They represent the number of "
            "injuries per one million hours worked.</p></div></section>")


def _event_trend(report):
    trend = report["event_trend"]
    head = "".join(f"<th>{escape(label)}</th>" for label in trend["labels"])
    rows = "".join(f'<tr><th scope="row">{escape(name)}</th>'
                   + "".join(f"<td>{value or '–'}</td>" for value in values) + "</tr>"
                   for name, values in trend["series"])
    return ('<section id="event-trend"><h2>Events by type &mdash; last 12 months</h2>'
            f'<div class="pad">{_stacked_bars("Events by type", trend["labels"], trend["series"])}'
            f'<details><summary>Show the numbers</summary><div class="scroll"><table><thead>'
            f"<tr><th>Type</th>{head}</tr></thead><tbody>{rows}</tbody></table></div></details>"
            '<p class="note">Mining and Exploration combined.</p></div></section>')


def _injuries(report):
    cards = []
    for title, items in report["injury_analysis"]:
        longest = max((n for _, n in items), default=1)
        bars = "".join(
            f'<span>{escape(label)}</span><span class="track"><span class="fill" '
            f'style="display:block;width:{n / longest * 100:.0f}%"></span></span>'
            f'<span class="n">{n}</span>' for label, n in items)
        inner = f'<div class="bars">{bars}</div>' if items else \
            '<p class="note">No injuries recorded in the last 12 months.</p>'
        cards.append(f'<div class="card"><h3>{escape(title)}</h3>{inner}</div>')
    return ('<section id="injury-analysis"><h2>Injury analysis &mdash; last 12 months</h2>'
            f'<div class="pad"><div class="cols">{"".join(cards)}</div></div></section>')


def _status(report):
    status = report["status"]
    tiles = "".join(f'<div class="tile stat"><b>{status[key]}</b><span>{label}</span></div>' for key, label in (
        ("events_open", "Events open (12 months)"),
        ("events_closed", "Events closed (12 months)"),
        ("actions_open", "Actions open"),
        ("actions_overdue", "Actions overdue"),
        ("actions_closed_month", "Actions closed in month")))
    return ('<section id="status"><h2>Open events and corrective actions</h2>'
            f'<div class="pad"><div class="bucket">{tiles}</div></div></section>')


def _footer():
    return ("<footer><p><strong>Source:</strong> PeopleTray. Rebuilt daily.</p>"
            "<p><strong>Mining:</strong> all CPO workgroups, Contractors &ndash; Local and "
            "Contractors &ndash; Other. <strong>Exploration:</strong> all GG workgroups and "
            "Drilling Contractors. Perth office and Flight/Accommodation Only are excluded.</p>"
            "<p><strong>Recordable injuries</strong> are lost time, restricted work and medically "
            "treated injuries. Non work related and pre-existing conditions are not counted.</p></footer>")


def render(report, logo_b64=None):
    main = "".join((_notice(report), _kpis(report), _table(report), _trends(report),
                    _event_trend(report), _injuries(report), _status(report), _footer()))
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>NMG Health &amp; Safety Performance</title><style>{CSS}</style></head><body>"
            f'{_header(report, logo_b64)}<div class="wrap">{main}</div></body></html>')
```

The status tiles use `class="tile stat"` so that exactly ten elements carry `class="tile"` (the KPI tiles), which `test_kpi_tiles` counts.

- [ ] **Step 5: Run to verify pass**

Run: `python -m pytest tests/test_render.py -q`
Expected: `13 passed`

- [ ] **Step 6: Commit**

```bash
git add render.py tests/test_render.py assets/nmg_logo.png
git commit -m "Add HTML and SVG rendering in NMG style"
```

---

### Task 7: Entry point, workflow and a live local build

**Files:**
- Create: `generate_dashboard.py`, `tests/test_generate.py`, `.github/workflows/dashboard.yml`
- Modify: `state.yaml`

**Interfaces:**
- Consumes: `fetch.fetch_all(today)`, `metrics.build_report(raw, today, generated)`, `render.render(report, logo_b64)`, `periods.today_perth()`, `periods.now_label()`.
- Produces: `generate_dashboard.build(raw, today, generated, out_path) -> dict` (writes the page, returns the report); `python generate_dashboard.py` writes `docs/index.html` and exits non-zero on any fetch failure.

- [ ] **Step 1: Write the failing test**

`tests/test_generate.py`:

```python
import generate_dashboard
from tests import sample


def test_build_writes_the_page(tmp_path):
    out = tmp_path / "docs" / "index.html"
    report = generate_dashboard.build(sample.RAW, sample.TODAY, "11 Oct 2026, 18:30 AWST", out)
    page = out.read_text(encoding="utf-8")
    assert report["month_label"] == "September 2026"
    assert page.startswith("<!doctype html>")
    assert "September 2026" in page
    assert "data:image/png;base64," in page       # the committed logo is embedded
    assert "Quixote" not in page
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_generate.py -q`
Expected: `ModuleNotFoundError: No module named 'generate_dashboard'`

- [ ] **Step 3: Write `generate_dashboard.py`**

```python
"""Build docs/index.html from live PeopleTray data."""
import base64
from pathlib import Path

import fetch
import metrics
import periods
import render

ROOT = Path(__file__).parent
LOGO = ROOT / "assets" / "nmg_logo.png"
OUTPUT = ROOT / "docs" / "index.html"


def build(raw, today, generated, out_path=OUTPUT):
    report = metrics.build_report(raw, today, generated)
    logo = base64.b64encode(LOGO.read_bytes()).decode("ascii") if LOGO.exists() else None
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render.render(report, logo), encoding="utf-8")
    return report


def main():
    today = periods.today_perth()
    report = build(fetch.fetch_all(today), today, periods.now_label())
    print(f"Built {OUTPUT} for {report['month_label']}")
    if report["unmapped"]:
        print(f"::warning::Unmapped workgroups left out of the figures: {', '.join(report['unmapped'])}")
    if report["undated"]:
        print(f"::warning::{report['undated']} events have no date and were not counted")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run all tests**

Run: `python -m pytest -q`
Expected: all pass, 0 failures.

- [ ] **Step 5: Build from live data and check the numbers**

Run: `python generate_dashboard.py`
Expected: `Built ...docs\index.html for September 2026` and no `::warning::` lines (a warning means a workgroup needs a bucket decision from Neil — stop and ask).

Then confirm the page against the figures verified on 2026-10-11 by opening `docs/index.html` and checking, for September 2026:

| Cell | Expected |
|---|---|
| Mining, First Aid Injury, September | 2 |
| Mining, Near Miss, September | 2 |
| Mining, Procedural Compliance, September | 2 |
| Mining, Property Damage / Loss, September | 4 |
| Mining, Total Person Hours Worked, September | 38,394 |
| Exploration, Total Person Hours Worked, September | 4,428 |
| Exploration, Lost Time Injury, FYTD | 1 |

Later corrections in PeopleTray can move these; a difference needs an explanation from the raw data, not a code change to force a match.

- [ ] **Step 6: Check the page in a browser**

Open `docs/index.html` with the Playwright browser tools at 1280 px and 390 px wide. Take a screenshot at each width and confirm: logo and header render; all six sections show; the table scrolls sideways on the phone width rather than overflowing; chart x-axis labels do not overlap; colours are NMG navy, river and gold. Fix anything wrong in `render.py`, re-run `python -m pytest -q`, rebuild.

- [ ] **Step 7: Write the workflow**

`.github/workflows/dashboard.yml`:

```yaml
name: NMG OHS Dashboard

on:
  schedule:
    # AWST = UTC+8. GitHub delivers schedule events late, so there are two
    # slots: either one alone keeps the page fresh for the day.
    - cron: '30 21 * * *'   # 05:30 AWST
    - cron: '0 4 * * *'     # 12:00 AWST
  workflow_dispatch:

permissions:
  contents: read

env:
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true

jobs:
  generate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5

      - uses: actions/setup-python@v6
        with:
          python-version: '3.12'

      - name: Run tests
        run: |
          python -m pip install --quiet pytest
          python -m pytest -q

      - name: Generate dashboard HTML
        run: python generate_dashboard.py
        env:
          PT_API_KEY: ${{ secrets.PT_API_KEY }}

      - name: Push to public site repo
        run: |
          git clone https://x-access-token:${{ secrets.PAGES_TOKEN }}@github.com/neil-noble/nmg-ohs-site.git /tmp/nmg-ohs-site
          cp docs/index.html /tmp/nmg-ohs-site/index.html
          cd /tmp/nmg-ohs-site
          git config user.name  "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add index.html
          git diff --staged --quiet || (
            git commit -m "Update dashboard $(date -u +'%Y-%m-%d %H:%M UTC')" &&
            git push
          )
```

A failed test or a failed fetch stops the job before the push step, so the last good page stays published.

- [ ] **Step 8: Update `state.yaml` and commit**

Set `phase: built_local` and `next: publish (Task 8) - needs Neil for repos, PAGES_TOKEN, Wix page`.

```bash
git add -A
git commit -m "Add entry point and publish workflow"
```

---

### Task 8: Publish (each outward-facing step is confirmed with Neil first)

**Files:**
- Modify: `state.yaml`

**Interfaces:**
- Consumes: the committed project and a passing local build from Task 7.
- Produces: the live page at `https://neil-noble.github.io/nmg-ohs-site/`, embedded at `/nmg-ohs`.

- [ ] **Step 1: Show Neil the locally built page and get his go-ahead to publish**

Send the two screenshots from Task 7 Step 6 and the September figures. Do not create anything on GitHub or Wix until he says yes. Remind him the Pages site is public (counts and rates only).

- [ ] **Step 2: Create the repos and push the source**

```bash
cd "/c/claude/NMG OHS Dashboard"
gh repo create neil-noble/nmg-ohs-dashboard --private --source . --remote origin --push
gh repo create neil-noble/nmg-ohs-site --public --description "NMG Health & Safety dashboard (generated)" --add-readme
```

- [ ] **Step 3: Set the secrets**

`PT_API_KEY` from the key file, without echoing it:

```bash
python -c "import peopletray, sys; sys.stdout.write(peopletray.load_key())" | gh secret set PT_API_KEY --repo neil-noble/nmg-ohs-dashboard
```

`PAGES_TOKEN`: Neil creates a fine-grained PAT in the GitHub UI (repository access: `nmg-ohs-site` only; permission: Contents read and write) and sets it himself so the token never passes through this session:

```
! gh secret set PAGES_TOKEN --repo neil-noble/nmg-ohs-dashboard
```

- [ ] **Step 4: Run the workflow and enable Pages**

```bash
gh workflow run dashboard.yml --repo neil-noble/nmg-ohs-dashboard --ref master
gh run watch --repo neil-noble/nmg-ohs-dashboard --exit-status
gh api -X POST repos/neil-noble/nmg-ohs-site/pages -f "source[branch]=main" -f "source[path]=/"
```

Expected: the run succeeds and `nmg-ohs-site` has an `index.html`. Then fetch `https://neil-noble.github.io/nmg-ohs-site/` (allow a few minutes) and confirm it contains "Health &amp; Safety Performance". If the Pages build sticks, use the recovery in the "Pages Deploy Recovery" memory (`POST /pages/builds`).

- [ ] **Step 5: Wix page**

With Neil's confirmation, add a page with the URL slug `nmg-ohs` on the Emergency Services Australia Wix site, containing an HTML embed (iframe) of `https://neil-noble.github.io/nmg-ohs-site/` at full width, and publish. If the Wix tools cannot create an embed, give Neil the three editor steps (Add → Embed Code → Embed a Site, paste the URL, set the page slug) instead. Verify `https://www.emergencyservicesaustralia.com.au/nmg-ohs` shows the dashboard.

- [ ] **Step 6: Record the live state**

Set `state.yaml` `phase: live` with both URLs and the go-live date, update the `project_nmg_ohs_dashboard.md` memory with the URLs and repos, commit and push.
