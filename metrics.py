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
