"""Raw PeopleTray lists in, one report dict out. Pure functions, no I/O."""
import calendar
from collections import Counter
from datetime import date

import config
from periods import (add_months, fy_start, long_label, month_end, month_range, parse_day,
                     rolling_12, short_label)

_COUNTED_CLASSES = tuple(code for code, _ in config.INJURY_CLASSES)
LTIFR_ROW = "Lost Time Injury Freq Rate (LTIFR)"
TRIFR_ROW = "Total Recordable Injury Freq Rate (TRIFR)"
# Most severe first: an event with several injured people is classed by its worst injury.
_SEVERITY = _COUNTED_CLASSES + config.NOT_COUNTED


def new_issues():
    """Things left out of the figures that a person needs to hear about."""
    return {"unmapped": set(), "undated": 0, "unclassified": 0}


def _text(value):
    return (value or "").strip()


def _first(details, field):
    return next((_text(d.get(field)) for d in details if _text(d.get(field))), "")


def _injury_class(event, details):
    """The event's own injury type, else the worst one on its injury rows, else its sub-type."""
    own = config.injury_code(event.get("injuryType"))
    if own:
        return own
    listed = [code for code in (config.injury_code(d.get("injuryType")) for d in details) if code]
    if listed:
        return min(listed, key=_SEVERITY.index)
    return config.classify_injury(None, _text(event.get("eventSubType"))
                                  or _first(details, "eventSubTypeName"))


def normalise_events(events, injuries, issues):
    # The injury list holds one row per injured person, so an event can have several.
    details_by_id = {}
    for detail in injuries:
        details_by_id.setdefault(str(detail.get("eventId")), []).append(detail)
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
        details = details_by_id.get(str(ev.get("eventId")), [])
        injury_class = None
        if _text(ev.get("eventType")) == config.INJURY_TYPE:
            injury_class = _injury_class(ev, details)
            if injury_class in config.NOT_COUNTED:
                continue
            if injury_class == config.UNCLASSIFIED:
                issues["unclassified"] += 1
            row = injury_class
        else:
            row = config.event_row(ev.get("eventType"))
            if row is None:
                continue
        out.append({
            "id": ev.get("eventId"), "day": day, "ym": (day.year, day.month),
            "bucket": which, "row": row, "injury_class": injury_class,
            "open": "open" in _text(ev.get("eventStatus")).lower(),
            "return_day": max(filter(None, (parse_day(d.get("returnWorkDate")) for d in details)),
                              default=None),
            "body": _first(details, "injuryBodyLocation"),
            "nature": _first(details, "injuryNature"),
            "mechanism": _first(details, "injuryMechanism"),
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
    """Rolling 12-month TRIFR and LTIFR for one area, or for both when bucket is COMBINED: both
    areas' injuries over both areas' hours, not an average of the two rates."""
    window = set(rolling_12(month))
    areas = config.BUCKETS if bucket == config.COMBINED else (bucket,)
    in_window = [e for b in areas for e in _in(events, b, window)]
    worked = sum(hours_sum(hours, b, window) for b in areas)
    recordable = sum(1 for e in in_window if e["injury_class"] in config.RECORDABLE)
    lost_time = sum(1 for e in in_window if e["injury_class"] == "LTI")
    return rate(recordable, worked), rate(lost_time, worked)


def head_count(people, bucket, as_at, issues=None):
    """NMG's own employees, no contractors, employed on the as_at day."""
    total = 0
    for p in people:
        if _text(p.get("employer")) != config.NMG_EMPLOYER:
            continue
        if _text(p.get("emplpyeeType")) == "Contractor":     # PeopleTray's spelling
            continue
        commenced, ceased = parse_day(p.get("dateCommenced")), parse_day(p.get("dateCeased"))
        if commenced and commenced > as_at:
            continue
        if ceased and ceased <= as_at:
            continue
        which = config.bucket(p.get("workGroup"))
        if which == config.UNMAPPED and issues is not None:
            issues["unmapped"].add(_text(p.get("workGroup")) or "(no workgroup)")
        if which == bucket:
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


def fy_columns(month):
    """(headings, month sets): each month of the financial year to `month`, then FYTD (Neil,
    2026-10-22, for both the Events and the Reports by area tables)."""
    fy_months = month_range(fy_start(month), month)
    return ([calendar.month_abbr[m] for _, m in fy_months] + ["FYTD"],
            [{m} for m in fy_months] + [set(fy_months)])


def build_table(events, hours, people, month, issues=None):
    periods = fy_columns(month)[1]
    last = len(periods) - 1

    def cells(value):
        """value(bucket, months, is_fytd) for each month then FYTD, Mining then Exploration."""
        return [value(b, months, i == last) for b in config.BUCKETS for i, months in enumerate(periods)]

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

    # Head count at the end of each month; only the reporting month's notes unmapped workgroups.
    table.append(line("NMG Head Count", cells(
        lambda b, months, fytd: "NA" if fytd else fmt_count(head_count(
            people, b, month_end(min(months)), issues if min(months) == month else None)))))
    table.append(line("Total Person Hours Worked", cells(
        lambda b, months, _: fmt_count(round(hours_sum(hours, b, months)))), bold=True))
    return table


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
             "trifr": {b: [] for b in config.BUCKETS + (config.COMBINED,)},
             "ltifr": {b: [] for b in config.BUCKETS + (config.COMBINED,)}}
    for point in points:
        for b in config.BUCKETS + (config.COMBINED,):
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


def build_injury_classes(events, month):
    """FYTD injuries per classification and bucket, for the classification chart."""
    fytd = set(month_range(fy_start(month), month))
    return [(label, {b: count(events, b, fytd, code) for b in config.BUCKETS})
            for code, label in config.INJURY_CLASSES]


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


def _days(n):
    return f"{n} day" if n == 1 else f"{n} days"


def _due_status(due, today):
    """(status text, overdue?) for something due on `due`."""
    if due is None:
        return "No due date", False
    if due < today:
        return f"Overdue {_days((today - due).days)}", True
    if due == today:
        return "Due today", False
    return f"Due in {_days((due - today).days)}", False


def _day_label(day):
    return f"{day.day} {calendar.month_abbr[day.month]} {day.year}" if day else "–"


def _name_key(name):
    return " ".join(_text(name).upper().split())


def contractor_lookup(people):
    """Each person's employer, by PeopleTray person id and by name.

    The events and actions feeds carry no company, so the contractor comes from the people
    feed. Current staff win over people who have left when two share a name.
    """
    by_id, by_name = {}, {}
    for p in sorted(people, key=lambda p: bool(p.get("dateCeased"))):
        employer = " ".join(_text(p.get("employer")).split())
        if not employer:
            continue
        if p.get("id") is not None:
            by_id.setdefault(p["id"], employer)
        for first in (p.get("firstName"), p.get("preferredName")):
            if _text(first):
                by_name.setdefault(_name_key(f"{first} {p.get('lastName') or ''}"), employer)
    return by_id, by_name


def build_open_actions(actions, today, people=()):
    """Outstanding corrective actions with their actionee and contractor, most overdue first.

    This and the open incidents are the places a person's name reaches the page: Neil asked
    for the actionee on 2026-10-11 and the contractor on 2026-10-19.
    """
    by_id, by_name = contractor_lookup(people)
    listed = []
    for a in actions:
        if _text(a.get("actionStatus")).lower() != "open":
            continue
        due = parse_day(a.get("dueDate"))
        status, overdue = _due_status(due, today)
        actionee = " ".join(_text(a.get("assignee")).split())
        listed.append((due is None, due or today, {
            "action": " ".join(_text(a.get("requiredAction")).split()) or "Not described",
            "actionee": actionee or "Unassigned",
            "contractor": by_id.get(a.get("assigneeId")) or by_name.get(_name_key(actionee)) or "–",
            "due": _day_label(due),
            "status": status,
            "overdue": overdue,
        }))
    listed.sort(key=lambda item: (item[0], item[1]))
    return [entry for _, _, entry in listed]


def build_open_incidents(events, people, today, keep=config.OPEN_INCIDENTS_SHOWN):
    """Open Mining and Exploration events, most overdue against their target close date first.

    The contractor is the employer of the person the event was reported to (Neil, 2026-10-19).
    The actionee is whoever holds the current step (Neil, 2026-10-22): the feed has no assignee
    (owner is always blank), so "Initiator to add information" goes back to the person who
    reported it and every other step sits with the person it was reported to.
    No description reaches the page: the free text names people, breath test breaches among them.
    """
    _, by_name = contractor_lookup(people)
    listed = []
    for ev in events:
        if "open" not in _text(ev.get("eventStatus")).lower():
            continue
        if config.bucket(ev.get("workGroup")) not in (config.MINING, config.EXPLORATION):
            continue
        day = parse_day(ev.get("eventDateTime")) or parse_day(ev.get("eventDate"))
        due = parse_day(ev.get("targetCloseDateTime")) or parse_day(ev.get("targetCloseDate"))
        status, overdue = _due_status(due, today)
        step = " ".join(_text(ev.get("currentStep")).split()) or "Open"
        holder = ev.get("reportedBy") if "initiator" in step.lower() else ev.get("reportedTo")
        listed.append((due is None, due or today, {
            "event": str(ev.get("eventId") or "–"),
            "date": _day_label(day),
            "type": _text(ev.get("eventType")) or "Not recorded",
            "workgroup": " ".join(_text(ev.get("workGroup")).split()),
            "step": step,
            "actionee": " ".join(_text(holder).split()) or "Unassigned",
            "contractor": by_name.get(_name_key(ev.get("reportedTo"))) or "–",
            "due": _day_label(due),
            "status": status.replace("No due date", "No target date"),
            "overdue": overdue,
        }))
    listed.sort(key=lambda item: (item[0], item[1]))
    return {"total": len(listed), "rows": [entry for _, _, entry in listed[:keep]]}


def build_open_workflows(events, checklists, keep=9):
    """Open workflows by type, the way PeopleTray's own chart slices them.

    Open checklists by name, plus every open event as "Safety Events". The API only returns
    submitted checklists, so forms issued but not yet submitted are missing from these counts.
    """
    tally = Counter()
    for c in checklists:
        name = " ".join(_text(c.get("checklistName")).split())
        if _text(c.get("workflowStatus")).lower() == "open" and name not in config.WORKFLOWS_NOT_CHARTED:
            tally[name or "Unnamed workflow"] += 1
    open_events = sum(1 for e in events if e["open"])
    if open_events:
        tally[config.SAFETY_EVENTS_WORKFLOW] = open_events
    ranked = sorted(tally.items(), key=lambda item: (-item[1], item[0]))
    if len(ranked) > keep + 1:
        ranked = ranked[:keep] + [("Other", sum(n for _, n in ranked[keep:]))]
    return ranked


def _hazard_reports(checklists):
    """(bucket, month) for each submitted Hazard Report Form in Mining or Exploration."""
    out = []
    for c in checklists:
        name = " ".join(_text(c.get("checklistName")).split())
        if name != config.HAZARD_REPORT_FORM or "discarded" in _text(c.get("workflowStatus")).lower():
            continue
        which = config.bucket(c.get("workgroup"))
        day = parse_day(c.get("checklistDateTime")) or parse_day(c.get("submitedDateTime"))
        if which in config.BUCKETS and day:
            out.append((which, (day.year, day.month)))
    return out


def build_reporting(events, checklists, month):
    """Near misses and hazard reports: by month for 12 months, one chart per area (Neil,
    2026-10-22), and a table with every month of the financial year so far, then FYTD."""
    points = rolling_12(month)
    columns, periods = fy_columns(month)
    near_misses = [(e["bucket"], e["ym"]) for e in events if e["row"] == config.NEAR_MISS_ROW]
    found = dict(zip(config.REPORTING_SERIES, (near_misses, _hazard_reports(checklists))))
    return {
        "labels": [short_label(p) for p in points],
        "series": {which: [(name, [sum(1 for b, ym in found[name] if b == which and ym == p)
                                   for p in points])
                            for name in config.REPORTING_SERIES]
                   for which in config.BUCKETS},
        "columns": columns,
        "table": [{"label": name, "bold": False,
                   "cells": [fmt_count(sum(1 for b, ym in found[name] if b == which and ym in months))
                             for which in config.BUCKETS for months in periods]}
                  for name in config.REPORTING_SERIES],
    }


def build_sheq_actions(actions, today):
    """PeopleTray's "SHEQ Actions" chart, reproduced from the actions feed.

    Its rule is not documented; this one reproduced its 5 / 1 / 3 on 2026-10-11: open actions
    whose actionee is in a Mining workgroup, split into Overdue (past the due date), Due
    (inside the action's reminder window) and Assigned (everything else).
    """
    assigned = due = overdue = 0
    for a in actions:
        if _text(a.get("actionStatus")).lower() != "open":
            continue
        if config.bucket(a.get("assigneeWorkgroup")) != config.MINING:
            continue
        due_day = parse_day(a.get("dueDate"))
        days_left = (due_day - today).days if due_day else None
        if days_left is None:
            assigned += 1
        elif days_left < 0:
            overdue += 1
        elif days_left <= int(a.get("reminderDays") or 0):
            due += 1
        else:
            assigned += 1
    return [("Assigned", assigned), ("Due", due), ("Overdue", overdue)]


def _qualified_on(competencies, day):
    """Employee ids Competent in every ERT qualification on `day`.

    A competency counts from its issue date to its expiry date; most carry neither, and then
    count throughout.
    """
    held = {}
    for c in competencies:
        name = _text(c.get("competencyName"))
        if c.get("workRole") != config.ERT_WORK_ROLE or not name.startswith("ERT: "):
            continue
        if _text(c.get("competencyStatus")) != "Competent":
            continue
        issued, expires = parse_day(c.get("competencyIssueDate")), parse_day(c.get("competencyExpiryDate"))
        if (issued and issued > day) or (expires and expires <= day):
            continue
        code = name[len("ERT: "):].split()[0] if name[len("ERT: "):].split() else ""
        held.setdefault(_text(c.get("employeeId")), set()).add(code)
    return {emp for emp, codes in held.items() if set(config.ERT_QUALIFICATIONS) <= codes}


def build_ozland_ert(people, roster, shift_types, competencies, today):
    """Did Ozland have 2 qualified ERT members on day shift and 2 on night shift, day by day?

    Counted the way the ERT dashboard counts its dials: today's ERT Members (work role), rostered
    on a shift PeopleTray flags as day or night. Days before PeopleTray holds a roster are left
    out rather than counted as a miss.
    """
    shifts = {s.get("id"): s for s in shift_types}
    ozland = {p.get("id"): _text(p.get("employeeId")) for p in people
              if config.ERT_WORK_ROLE in (p.get("workRoles") or [])
              and config.OZLAND_EMPLOYER in _text(p.get("employer")).lower()}
    on_shift, rostered = {}, set()
    for r in roster:
        day = parse_day(r.get("rosterDate"))
        if day is None or day > today:
            continue
        rostered.add(day)
        if r.get("personId") not in ozland:
            continue
        shift = shifts.get(r.get("shiftTypeId")) or {}
        which = "day" if shift.get("isDayshift") else "night" if shift.get("isNightshift") else None
        if which:
            on_shift.setdefault((day, which), set()).add(ozland[r.get("personId")])
    days = []
    for day in sorted(rostered):
        qualified = _qualified_on(competencies, day)
        crew = {which: len(on_shift.get((day, which), set()) & qualified) for which in ("day", "night")}
        days.append({"day": day, "label": _day_label(day), "day_shift": crew["day"],
                     "night_shift": crew["night"],
                     "met": min(crew.values()) >= config.OZLAND_ERT_PER_SHIFT})
    met = sum(1 for d in days if d["met"])
    return {"days": days, "met": met, "missed": len(days) - met,
            "fy_start": date(*fy_start((today.year, today.month)), 1)}


def build_report(raw, today, generated):
    month = add_months((today.year, today.month), -1)
    issues = new_issues()
    events = normalise_events(raw["events"], raw["injuries"], issues)
    hours = normalise_hours(raw["hours"], issues)
    table = build_table(events, hours, raw["people"], month, issues)     # adds to issues
    open_actions = build_open_actions(raw["actions"], today, raw["people"])
    # PeopleTray's own two charts, read off its SHEQ home page, win over the API reconstructions.
    web = raw.get("web_charts")
    if web:
        source = "web"
        sheq_actions = list(web["sheq_actions"])
        open_workflows = sorted(((name, n) for name, n in web["open_workflows"]
                                 if n and name not in config.WORKFLOWS_NOT_CHARTED),
                                key=lambda item: (-item[1], item[0]))
    else:
        source = "api_fallback" if raw.get("web_error") else "api"
        sheq_actions = build_sheq_actions(raw["actions"], today)
        open_workflows = build_open_workflows(events, raw.get("checklists", []))
    return {
        "month_label": long_label(month),
        "generated": generated,
        "kpis": build_kpis(events, hours, month, today),
        "table": table,
        "table_columns": fy_columns(month)[0],
        "trend": build_trend(events, hours, month),
        "event_trend": build_event_trend(events, month),
        "reporting": build_reporting(events, raw.get("checklists", []), month),
        "injury_analysis": build_injury_analysis(events, month),
        "injury_classes": build_injury_classes(events, month),
        "status": build_status(events, raw["actions"], month, today),
        "open_actions": open_actions,
        "open_incidents": build_open_incidents(raw["events"], raw["people"], today),
        "ozland_ert": build_ozland_ert(raw["people"], raw.get("roster", []), raw.get("shifttypes", []),
                                       raw.get("competencies", []), today),
        "open_workflows": open_workflows,
        "sheq_actions": sheq_actions,
        "charts_source": source,
        "unmapped": sorted(issues["unmapped"]),
        "undated": issues["undated"],
        "unclassified": issues["unclassified"],
    }
