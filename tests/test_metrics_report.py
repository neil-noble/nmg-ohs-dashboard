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
        ("TRIFR", "64.52"), ("LTIFR", "64.52"), ("Injuries in month", "–"),
        ("Days since last LTI", "58"), ("Person hours in month", "3,000")]


def test_trend_has_12_labelled_points(report):
    trend = report["trend"]
    assert len(trend["labels"]) == 12
    assert trend["labels"][0] == "Oct 25" and trend["labels"][-1] == "Sep 26"
    assert trend["trifr"][config.EXPLORATION][-1] == pytest.approx(64.516129)
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
