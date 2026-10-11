"""Raw PeopleTray lists in, one report dict out. Pure functions, no I/O."""
from collections import Counter

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
    window = set(rolling_12(month))
    in_window = _in(events, bucket, window)
    worked = hours_sum(hours, bucket, window)
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


def build_table(events, hours, people, month, issues=None):
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
        lambda b, _, fytd: "NA" if fytd else fmt_count(head_count(people, b, as_at, issues)))))
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
    table = build_table(events, hours, raw["people"], month, issues)     # adds to issues
    return {
        "month_label": long_label(month),
        "generated": generated,
        "kpis": build_kpis(events, hours, month, today),
        "table": table,
        "trend": build_trend(events, hours, month),
        "event_trend": build_event_trend(events, month),
        "injury_analysis": build_injury_analysis(events, month),
        "status": build_status(events, raw["actions"], month, today),
        "unmapped": sorted(issues["unmapped"]),
        "undated": issues["undated"],
        "unclassified": issues["unclassified"],
    }
