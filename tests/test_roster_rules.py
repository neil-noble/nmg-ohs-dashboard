"""The Ozland ERT record is only built from a roster read that passes roster_check.verify.

Neil, 2026-11-14: no errors reading the PeopleTray roster. Do not delete or weaken.
"""
from datetime import date

import pytest

import config
import fetch
import metrics
import roster_check

TODAY = date(2026, 11, 14)
TYPES = [
    {"id": 1, "statusName": "Dayshift", "isDayshift": True, "isNightshift": False, "isOffsite": False},
    {"id": 2, "statusName": "Nightshift", "isDayshift": False, "isNightshift": True, "isOffsite": False},
]
PEOPLE = [{"id": 1, "employeeId": "700", "workRoles": [config.ERT_WORK_ROLE], "employer": "Ozland Drill and Blast"},
          {"id": 2, "employeeId": "701", "workRoles": [], "employer": "Someone Else"}]


def row(person, shift, day="2026-11-14T00:00:00"):
    return {"personId": person, "shiftTypeId": shift, "rosterDate": day, "lastName": "SECRET", "firstName": "Name"}


def test_a_clean_roster_builds_the_record():
    record = metrics.build_ozland_ert(PEOPLE, [row(1, 1), row(2, 2)], TYPES, [], TODAY)
    assert [d["day"] for d in record["days"]] == [TODAY]


def test_an_ozland_member_with_two_shifts_stops_the_build_without_naming_them():
    with pytest.raises(roster_check.RosterError, match="person id 1 has two different shifts") as caught:
        metrics.build_ozland_ert(PEOPLE, [row(1, 1), row(1, 2)], TYPES, [], TODAY)
    assert "SECRET" not in str(caught.value)          # the build log is public


def test_an_unknown_shift_type_stops_the_build():
    with pytest.raises(roster_check.RosterError, match="not in PeopleTray's shift types"):
        metrics.build_ozland_ert(PEOPLE, [row(1, 99)], TYPES, [], TODAY)


def test_someone_elses_bad_row_does_not():
    metrics.build_ozland_ert(PEOPLE, [row(1, 1), row(2, 1), row(2, 2)], TYPES, [], TODAY)


def test_a_row_from_before_the_financial_year_stops_the_build():
    with pytest.raises(roster_check.RosterError, match="2026-06-30"):
        metrics.build_ozland_ert(PEOPLE, [row(1, 1), row(1, 1, "2026-06-30T00:00:00")], TYPES, [], TODAY)


def test_the_roster_and_shift_type_feeds_may_never_come_back_empty():
    assert {"roster", "shifttypes"} <= set(fetch._CORE)
