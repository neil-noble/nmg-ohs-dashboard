"""End of Month Report hours for a finished month the exposure hours feed lacks (Neil, 2026-11-07)."""
from datetime import date, datetime, timedelta, timezone

import eomhours
import generate_dashboard
import metrics
from tests import sample

CODES = {"Day Shift": "DS", "Night Shift": "NS", "Expl Day": "ED", "Fly In": "FIA", "Fly Out": "FOA",
         "R&R": "RR"}


def row(day, workgroup, shift, hours, employer="New Murchison Gold Ltd", first="Ann", last="Lee", pid="1"):
    return {"Date": day, "Employee Id": pid, "First Name": first, "Last Name": last, "Employer": employer,
            "Workgroup": workgroup, "Shift Type": shift, "Exp Hours": hours}


def test_allocate_follows_the_eom_rules():
    rows = [
        row("05-Oct-2026", "CPO - Geology", "Day Shift", 12),
        row("06-Oct-2026", "PER - Finance", "Day Shift", 8, pid="2"),
        row("07-Oct-2026", "Contractors - Local", "Day Shift", 12, pid="3"),           # excluded
        row("08-Oct-2026", "GG - Exploration", "Expl Day", 10, pid="4"),
        row("09-Oct-2026", "GG - Exploration", "Day Shift", 12, pid="4"),              # on a mining shift
        row("10-Oct-2026", "Flight/Accommodation ONLY", "Day Shift", 12, employer="Ozland Drill and Blast", pid="5"),
        row("10-Oct-2026", "Flight/Accommodation ONLY", "R&R", 12, employer="Other Co", pid="6"),
        row("11-Oct-2026", "CPO - Geology", "Day Shift", 12, first="Dummy", pid="7"),  # placeholder
        row("11-Oct-2026", "CPO - Geology", "Day Shift", 12, employer="Westgold", pid="8"),
        row("30-Sep-2026", "CPO - Geology", "Day Shift", 12),                          # other month
    ]
    assert eomhours.allocate(rows, CODES, (2026, 10)) == {"Mining": 44.0, "Exploration": 10.0}


def test_missing_months_are_the_finished_months_after_the_feed():
    feed = {("Mining", (2026, 9)): 38394.0, ("Exploration", (2026, 9)): 4428.0}
    assert eomhours.missing_months(feed, (2026, 11)) == [(2026, 10)]
    assert eomhours.missing_months(feed, (2026, 10)) == []
    assert eomhours.missing_months(feed, (2027, 3)) == [(2026, 10), (2026, 11)]
    assert eomhours.missing_months({}, (2026, 11)) == []


def test_no_web_login_means_no_report():
    assert eomhours.fetch_eom_hours([(2026, 10)], [], {}) == {}


def test_report_hours_fill_a_missing_month_and_move_the_rates_on():
    raw = dict(sample.RAW, eom_hours={(2026, 10): {"Mining": 40000.0, "Exploration": 6000.0}})
    today = date(2026, 11, 7)
    report = metrics.build_report(raw, today, "now")
    assert report["rates_to"] == "October 2026"
    assert report["hours_from_eom"] == ["October 2026"]
    plain = metrics.build_report(sample.RAW, today, "now")
    assert plain["hours_from_eom"] == [] and plain["rates_to"] != "October 2026"


def test_the_feed_wins_over_the_report():
    raw = dict(sample.RAW, eom_hours={sample.MONTH: {"Mining": 1.0, "Exploration": 1.0}})
    report = metrics.build_report(raw, sample.TODAY, "now")
    assert report["hours_from_eom"] == []


def test_read_eom_hours_caches_and_never_raises(tmp_path):
    cache = tmp_path / "eomhours.json"
    today, now = date(2026, 11, 7), datetime(2026, 11, 7, 8, tzinfo=timezone.utc)
    calls = []

    def fetcher(months, shifttypes, env):
        calls.append(months)
        return {m: {"Mining": 5.0, "Exploration": 1.0} for m in months}

    raw = {"hours": sample.RAW["hours"]}
    wanted = eomhours.missing_months(metrics.normalise_hours(raw["hours"], metrics.new_issues()), (2026, 11))
    found, error = generate_dashboard.read_eom_hours(raw, today, cache, now, fetcher)
    assert error is None and set(found) == set(wanted) and len(calls) == 1
    again, _ = generate_dashboard.read_eom_hours(raw, today, cache, now + timedelta(hours=1), fetcher)
    assert again == found and len(calls) == 1                       # from the cache
    generate_dashboard.read_eom_hours(raw, today, cache, now + timedelta(hours=7), fetcher)
    assert len(calls) == 2                                          # stale: fetched again

    def broken(months, shifttypes, env):
        raise eomhours.EomHoursError("sign-in rejected")

    assert generate_dashboard.read_eom_hours(raw, today, None, now, broken) == ({}, "sign-in rejected")


def test_the_note_names_the_report_months():
    import render
    note = render._rates_note({"rates_to": "October 2026", "month_label": "November 2026",
                               "hours_from_eom": ["October 2026"]})
    assert "October 2026 person hours are from PeopleTray's End of Month Report" in note
