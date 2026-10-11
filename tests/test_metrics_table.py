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
    assert metrics.rate(1, 15500.0) == pytest.approx(64.516129)
    assert metrics.rate(0, 1000.0) == 0.0
    assert metrics.rate(3, 0) is None
    assert metrics.fmt_rate(64.516129) == "64.52"
    assert metrics.fmt_rate(0.0) == "0.00"
    assert metrics.fmt_rate(None) == "NA"
    assert metrics.fmt_count(0) == "–"
    assert metrics.fmt_count(38826) == "38,826"


def test_frequency_rates_use_rolling_12_months(data):
    events, hours, _ = data
    trifr, ltifr = metrics.frequency_rates(events, hours, config.EXPLORATION, sample.MONTH)
    assert trifr == pytest.approx(64.516129) and ltifr == pytest.approx(64.516129)
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
    assert row(table, "Lost Time Injury Freq Rate (LTIFR)") == ["NA", "0.00", "NA", "64.52"]
    assert row(table, "Total Recordable Injury Freq Rate (TRIFR)") == ["NA", "0.00", "NA", "64.52"]
    assert row(table, "Environmental Incidents") == ["–", "–", "–", "–"]
    assert row(table, "Property Damage / Loss") == ["1", "1", "–", "–"]
    assert row(table, "Security Incident / Violence") == ["–", "1", "–", "1"]
    assert row(table, "Misfire") == ["1", "1", "–", "–"]
    assert row(table, "NMG Head Count") == ["2", "NA", "1", "NA"]
    assert row(table, "Total Person Hours Worked") == ["30,500", "90,500", "3,000", "6,500"]


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
