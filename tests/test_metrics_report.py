import pytest

import config
import metrics
from tests import sample


@pytest.fixture(scope="module")
def report():
    return metrics.build_report(sample.RAW, sample.TODAY, "11 Oct 2026, 18:30 AWST")


def test_report_keys(report):
    assert set(report) == {"month_label", "generated", "kpis", "table", "trend", "event_trend",
                           "injury_analysis", "status", "unmapped", "undated",
                           "unclassified", "injury_classes",
                           "open_actions", "open_workflows", "sheq_actions",
                           "overdue_history", "overdue_since", "charts_source"}
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


def test_report_carries_unclassified_count_and_head_count_workgroups():
    raw = {"events": [sample.event(1, "2026-09-03", "CPO - Ozland", "Injury", "", "")],
           "injuries": [], "hours": [], "actions": [], "people": [sample.person("Processing - Mill")]}
    report = metrics.build_report(raw, sample.TODAY, "x")
    assert report["unclassified"] == 1
    assert report["unmapped"] == ["Processing - Mill"]


def test_injury_classes_are_fytd_counts_per_bucket(report):
    classes = {label: values for label, values in report["injury_classes"]}
    assert list(classes) == ["Lost Time Injury", "Restricted Work Injury", "Medically Treated Injury",
                             "First Aid Injury", "No Treatment Injury"]
    assert classes["First Aid Injury"] == {config.MINING: 2, config.EXPLORATION: 0}
    assert classes["Lost Time Injury"] == {config.MINING: 0, config.EXPLORATION: 1}
    assert classes["No Treatment Injury"] == {config.MINING: 0, config.EXPLORATION: 0}   # June is last FY


def test_open_actions_are_listed_most_overdue_first(report):
    assert report["open_actions"] == [
        {"action": "Fit the <new> guard", "actionee": "Otto OWNER", "due": "2 Oct 2026",
         "status": "Overdue 9 days", "overdue": True},
        {"action": "Review the ore mark-up procedure", "actionee": "Petra ACTIONEE",
         "due": "1 Nov 2026", "status": "Due in 21 days", "overdue": False},
    ]


def test_open_action_edge_cases():
    actions = [sample.action("Open", due=None, assignee=None, required=None),
               sample.action("Open", due="2026-10-11T00:00:00", assignee="A", required="Today"),
               sample.action("Open", due="2026-10-10T00:00:00", assignee="B", required="Yesterday"),
               sample.action(" open ", due="2026-10-12T00:00:00", assignee="C", required="Tomorrow"),
               sample.action("Closed complete", due="2026-10-01T00:00:00", assignee="D", required="Done")]
    listed = metrics.build_open_actions(actions, sample.TODAY)
    assert [(a["action"], a["status"], a["overdue"]) for a in listed] == [
        ("Yesterday", "Overdue 1 day", True), ("Today", "Due today", False),
        ("Tomorrow", "Due in 1 day", False), ("Not described", "No due date", False)]
    assert listed[-1]["actionee"] == "Unassigned" and listed[-1]["due"] == "–"


def test_open_workflows_by_workflow_type(report):
    # Open checklists by name plus open safety events; HR forms PeopleTray leaves off are dropped.
    assert report["open_workflows"] == [("Take 5", 2), ("Prestart - Light Vehicles", 1),
                                        ("Safety Events", 1)]


def test_open_workflows_count_every_open_event_whatever_its_date():
    events = [sample.event(1, "2026-10-05", "CPO - Ozland", "Injury", "First Aid Injury", status="Open Workflow"),
              sample.event(2, "2025-01-05", "CPO - Ozland", "Injury", "No Treatment Required", status="Open Workflow"),
              sample.event(3, "2026-10-06", "GG - Exploration", "Misfire", status="Open Workflow"),
              sample.event(4, "2026-10-06", "CPO - Ozland", "Misfire"),
              sample.event(5, "2026-10-06", "PER - Finance", "Misfire", status="Open Workflow")]
    raw = dict(sample.RAW, events=events, injuries=[], checklists=[])
    assert metrics.build_report(raw, sample.TODAY, "x")["open_workflows"] == [("Safety Events", 3)]


def test_sheq_actions_assigned_due_and_overdue(report):
    assert report["sheq_actions"] == [("Assigned", 1), ("Due", 0), ("Overdue", 1)]


def test_overdue_history_ranks_actionees(report):
    assert report["overdue_history"] == [
        {"actionee": "Otto OWNER", "late": 1, "still": 1, "assigned": 2}]
    assert report["overdue_since"] == "Jul 2025"


def test_overdue_history_rules():
    A = sample.action
    actions = [
        A("Closed complete", due="2026-09-10T00:00:00", completed="2026-09-10T23:00:00", assignee="On Time"),
        A("Closed complete", due="2026-09-10T00:00:00", completed="2026-09-11T01:00:00", assignee="One Late"),
        A("Closed non implemented", due="2026-09-10T00:00:00", completed=None, assignee="No Date"),
        A("Open", due="2026-10-11T00:00:00", assignee="Due Today"),
        A("Open", due="2026-10-01T00:00:00", assignee="Two  Late"),
        A("Closed partially complete", due="2026-08-01T00:00:00", completed="2026-08-09T00:00:00", assignee="Two Late"),
        A("Open", due="2026-10-01T00:00:00", assignee=None),
    ]
    history = metrics.build_overdue_history(actions, sample.TODAY)
    assert history == [
        {"actionee": "Two Late", "late": 1, "still": 1, "assigned": 2},
        {"actionee": "Unassigned", "late": 0, "still": 1, "assigned": 1},   # ties: still overdue first
        {"actionee": "One Late", "late": 1, "still": 0, "assigned": 1},
    ]


def test_overdue_history_keeps_the_ten_worst():
    actions = [sample.action("Open", due="2026-10-01T00:00:00", assignee=f"Person {i:02d}") for i in range(12)]
    assert len(metrics.build_overdue_history(actions, sample.TODAY)) == 10


def test_sheq_actions_follow_peopletrays_chart():
    A = sample.action
    actions = [
        A("Open", due="2026-10-23T00:00:00"),                       # outside the reminder window
        A("Open", due="2026-10-14T00:00:00", reminder=2),           # 3 days out, reminder 2
        A("Open", due="2026-10-13T00:00:00", reminder=2),           # inside the window
        A("Open", due="2026-10-11T00:00:00", reminder=None),        # due today
        A("Open", due="2026-10-10T00:00:00"),                       # overdue
        A("Open", due=None),                                        # no due date
        A("Open", due="2026-09-30T00:00:00", workgroup="GG - Exploration"),      # not on PeopleTray's chart
        A("Open", due="2026-09-28T00:00:00", workgroup="Drilling Contractors"),
        A("Closed complete", due="2026-09-01T00:00:00", completed="2026-09-20T00:00:00"),
    ]
    assert metrics.build_sheq_actions(actions, sample.TODAY) == [("Assigned", 3), ("Due", 2), ("Overdue", 1)]


def test_open_workflows_keep_the_nine_biggest_types():
    lists = [sample.checklist(f"Form {i:02d}") for i in range(12) for _ in range(12 - i)]
    raw = dict(sample.RAW, events=[], injuries=[], checklists=lists)
    slices = metrics.build_report(raw, sample.TODAY, "x")["open_workflows"]
    assert len(slices) == 10 and slices[0] == ("Form 00", 12)
    assert slices[-1] == ("Other", 3 + 2 + 1)


def test_report_builds_without_a_checklist_feed():
    raw = {k: v for k, v in sample.RAW.items() if k != "checklists"}
    assert metrics.build_report(raw, sample.TODAY, "x")["open_workflows"] == [("Safety Events", 1)]


WEB = {"sheq_actions": [("Assigned", 5), ("Due", 1), ("Overdue", 3)],
       "open_workflows": [("CCV - Explosives", 1), ("Take 5", 18), ("Nothing open", 0),
                          ("Light Vehicle Prestarts", 107), ("Area Inspection", 7)]}


def test_without_web_charts_the_api_figures_are_used(report):
    assert report["charts_source"] == "api"


def test_web_charts_replace_the_api_versions_of_both_charts():
    report = metrics.build_report(dict(sample.RAW, web_charts=WEB), sample.TODAY, "x")
    assert report["charts_source"] == "web"
    assert report["sheq_actions"] == [("Assigned", 5), ("Due", 1), ("Overdue", 3)]
    assert report["open_workflows"] == [("Light Vehicle Prestarts", 107), ("Take 5", 18),
                                        ("Area Inspection", 7), ("CCV - Explosives", 1)]


def test_a_failed_web_read_falls_back_to_the_api_and_says_so():
    report = metrics.build_report(dict(sample.RAW, web_charts=None, web_error="sign-in rejected"),
                                  sample.TODAY, "x")
    assert report["charts_source"] == "api_fallback"
    assert report["sheq_actions"] == [("Assigned", 1), ("Due", 0), ("Overdue", 1)]


def test_web_pie_keeps_every_slice_peopletray_shows():
    web = dict(WEB, open_workflows=[(f"Workflow {i:02d}", 20 - i) for i in range(14)])
    report = metrics.build_report(dict(sample.RAW, web_charts=web), sample.TODAY, "x")
    assert len(report["open_workflows"]) == 14
