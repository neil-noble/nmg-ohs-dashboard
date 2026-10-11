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
