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


def month_and_fytd(cells):
    """September and FYTD for Mining then Exploration, out of Jul, Aug, Sep, FYTD for each."""
    return [cells[2], cells[3], cells[6], cells[7]]


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
    assert month_and_fytd(row(table, "Lost Time Injury")) == ["–", "–", "–", "1"]
    assert month_and_fytd(row(table, "Restricted Work Injury")) == ["–", "–", "–", "–"]
    assert month_and_fytd(row(table, "First Aid Injury")) == ["2", "2", "–", "–"]
    assert month_and_fytd(row(table, "No Treatment Injury")) == ["–", "–", "–", "–"]   # June is last FY
    assert month_and_fytd(row(table, "Total Injuries")) == ["2", "2", "–", "1"]
    assert month_and_fytd(row(table, "Near Miss")) == ["2", "2", "–", "–"]
    assert month_and_fytd(row(table, "Lost Workdays")) == ["–", "–", "–", "open"]
    assert month_and_fytd(row(table, "Lost Time Injury Freq Rate (LTIFR)")) == ["NA", "0.00", "NA", "64.52"]
    assert month_and_fytd(row(table, "Total Recordable Injury Freq Rate (TRIFR)")) == ["NA", "0.00", "NA", "64.52"]
    assert month_and_fytd(row(table, "Environmental Incidents")) == ["–", "–", "–", "–"]
    assert month_and_fytd(row(table, "Property Damage / Loss")) == ["1", "1", "–", "–"]
    assert month_and_fytd(row(table, "Security Incident / Violence")) == ["–", "1", "–", "1"]
    assert month_and_fytd(row(table, "Misfire")) == ["1", "1", "–", "–"]
    assert month_and_fytd(row(table, "NMG Head Count")) == ["2", "NA", "1", "NA"]
    assert month_and_fytd(row(table, "Total Person Hours Worked")) == ["30,500", "90,500", "3,000", "6,500"]


def test_table_has_every_month_of_the_financial_year(data):
    # Jul, Aug, Sep then FYTD, for Mining then Exploration (Neil, 2026-10-22).
    events, hours, _ = data
    table = metrics.build_table(events, hours, sample.PEOPLE, sample.MONTH)
    assert all(len(r["cells"]) == 8 for r in table)
    assert row(table, "Lost Time Injury") == ["–", "–", "–", "–", "–", "1", "–", "1"]
    assert row(table, "Security Incident / Violence") == ["–", "1", "–", "1", "1", "–", "–", "1"]
    assert row(table, "Lost Time Injury Freq Rate (LTIFR)")[3] == "0.00"
    assert row(table, "NMG Head Count")[3] == "NA" and row(table, "NMG Head Count")[7] == "NA"
    assert metrics.fy_columns(sample.MONTH)[0] == ["Jul", "Aug", "Sep", "FYTD"]
    assert metrics.fy_columns((2026, 7))[0] == ["Jul", "FYTD"]


def test_combined_rates_pool_injuries_and_hours(data):
    events, hours, _ = data
    trifr, ltifr = metrics.frequency_rates(events, hours, config.COMBINED, sample.MONTH)
    mining_hours = sum(hours.get((config.MINING, m), 0) for m in metrics.rolling_12(sample.MONTH))
    exploration_hours = sum(hours.get((config.EXPLORATION, m), 0) for m in metrics.rolling_12(sample.MONTH))
    # Exploration's one LTI in 12 months over both areas' hours.
    assert ltifr == pytest.approx(1_000_000 / (mining_hours + exploration_hours))
    assert trifr == pytest.approx(ltifr)


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
    assert month_and_fytd(row(table, "Fire & <Explosion>")) == ["1", "1", "–", "–"]
    assert month_and_fytd(row(table, "Unclassified injury")) == ["1", "1", "–", "–"]
    assert month_and_fytd(row(table, "Total Injuries")) == ["1", "1", "–", "–"]


def test_lost_workdays_with_a_return_date():
    issues = metrics.new_issues()
    ev = sample.event(1, "2026-09-10", "CPO - Ozland", "Injury", "Lost Time Injury", "")
    events = metrics.normalise_events(
        [ev], [sample.injury(1, returnWorkDate="2026-09-17T00:00:00")], issues)
    table = metrics.build_table(events, {}, [], sample.MONTH)
    assert month_and_fytd(row(table, "Lost Workdays")) == ["7", "7", "–", "–"]


def test_empty_data_renders_dashes_and_na_without_dividing_by_zero():
    table = metrics.build_table([], {}, [], sample.MONTH)
    assert month_and_fytd(row(table, "Total Injuries")) == ["–", "–", "–", "–"]
    assert month_and_fytd(row(table, "Lost Time Injury Freq Rate (LTIFR)")) == ["NA", "NA", "NA", "NA"]
    # No hours for the reporting month means PeopleTray does not have them yet
    assert month_and_fytd(row(table, "Total Person Hours Worked")) == ["Pending", "–", "Pending", "–"]
    assert month_and_fytd(row(table, "NMG Head Count")) == ["–", "NA", "–", "NA"]


def test_most_severe_injury_row_wins_when_an_event_has_several():
    ev = sample.event(1, "2026-09-01", "CPO - Ozland", "Injury", "First Aid Injury", "")
    rows = [sample.injury(1),
            sample.injury("1", injuryType="LTI (Lost Time Injury) ",
                          returnWorkDate="2026-09-20T00:00:00", injuryBodyLocation="Back")]
    event = metrics.normalise_events([ev], rows, metrics.new_issues())[0]
    assert event["injury_class"] == "LTI"
    assert event["return_day"] == date(2026, 9, 20)
    assert event["body"] == "Back"


def test_unknown_event_injury_type_does_not_block_the_injury_list():
    ev = sample.event(1, "2026-09-01", "CPO - Ozland", "Injury", "No Treatment Required", "Pending review")
    rows = [sample.injury(1, injuryType="MTI(Medical Treatment Injury)")]
    assert metrics.normalise_events([ev], rows, metrics.new_issues())[0]["injury_class"] == "MTI"


def test_trifr_counts_restricted_and_medical_injuries_but_ltifr_does_not():
    issues = metrics.new_issues()
    events = metrics.normalise_events([
        sample.event(1, "2026-09-01", "CPO - Ozland", "Injury", "Lost Time Injury"),
        sample.event(2, "2026-09-02", "CPO - Ozland", "Injury", "Restricted Work Injury"),
        sample.event(3, "2026-09-03", "CPO - Ozland", "Injury", "Medical Treatment Injury"),
        sample.event(4, "2026-09-04", "CPO - Ozland", "Injury", "First Aid Injury"),
    ], [], issues)
    hours = metrics.normalise_hours([sample.hours("CPO - Ozland", 2026, 9, 1_000_000.0)], issues)
    assert metrics.frequency_rates(events, hours, config.MINING, sample.MONTH) == (3.0, 1.0)


def test_head_count_reports_nmg_employees_in_unmapped_workgroups():
    issues = metrics.new_issues()
    people = [sample.person("Processing - Mill"), sample.person(None),
              sample.person("Shutdown Crew", employer="Another Company")]
    assert metrics.head_count(people, config.MINING, date(2026, 9, 30), issues) == 0
    assert issues["unmapped"] == {"Processing - Mill", "(no workgroup)"}


def test_unclassified_injuries_are_counted_as_an_issue():
    issues = metrics.new_issues()
    metrics.normalise_events([sample.event(1, "2026-09-03", "CPO - Ozland", "Injury", "", "")], [], issues)
    assert issues["unclassified"] == 1
