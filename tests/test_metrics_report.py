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
                           "charts_source", "open_incidents", "table_columns", "close_out",
                           "ozland_ert", "reporting"}
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
    assert len(trend["trifr"][config.COMBINED]) == 12 and len(trend["ltifr"][config.COMBINED]) == 12


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
        {"action": "Fit the <new> guard", "actionee": "Otto OWNER", "contractor": "Acme Haulage",
         "due": "2 Oct 2026", "status": "Overdue 9 days", "overdue": True},
        {"action": "Review the ore mark-up procedure", "actionee": "Petra ACTIONEE",
         "contractor": "Petra & Sons", "due": "1 Nov 2026", "status": "Due in 21 days",
         "overdue": False},
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
    # Light vehicle prestarts are left off too (Neil, 2026-10-22).
    assert report["open_workflows"] == [("Take 5", 2), ("Safety Events", 1)]


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
    assert report["open_workflows"] == [("Take 5", 18), ("Area Inspection", 7), ("CCV - Explosives", 1)]


def test_a_failed_web_read_falls_back_to_the_api_and_says_so():
    report = metrics.build_report(dict(sample.RAW, web_charts=None, web_error="sign-in rejected"),
                                  sample.TODAY, "x")
    assert report["charts_source"] == "api_fallback"
    assert report["sheq_actions"] == [("Assigned", 1), ("Due", 0), ("Overdue", 1)]


def test_web_pie_keeps_every_slice_peopletray_shows():
    web = dict(WEB, open_workflows=[(f"Workflow {i:02d}", 20 - i) for i in range(14)])
    report = metrics.build_report(dict(sample.RAW, web_charts=web), sample.TODAY, "x")
    assert len(report["open_workflows"]) == 14


def test_exploration_daily_prestart_is_left_off_the_open_workflows_pie():
    web = dict(WEB, open_workflows=[("Take 5", 18), ("Exploration Daily Prestart", 8),
                                    ("Exploration Monthly LV Inspection", 2)])
    from_web = metrics.build_report(dict(sample.RAW, web_charts=web), sample.TODAY, "x")["open_workflows"]
    assert from_web == [("Take 5", 18), ("Exploration Monthly LV Inspection", 2)]
    lists = [sample.checklist("Exploration Daily Prestart"), sample.checklist("Take 5")]
    from_api = metrics.build_report(dict(sample.RAW, checklists=lists), sample.TODAY, "x")["open_workflows"]
    assert from_api == [("Safety Events", 1), ("Take 5", 1)]


def test_action_contractor_prefers_the_person_id_then_the_name():
    people = [sample.person("CPO - Ozland", employer="Old Co", pid=7, first="Al", last="SMITH",
                            ceased="2025-01-01T00:00:00"),
              sample.person("CPO - Ozland", employer="New Co", pid=8, first="Al", last="SMITH"),
              sample.person("CPO - Ozland", employer="Id Co", pid=9, first="Bo", last="JONES")]
    actions = [sample.action("Open", due="2026-10-01T00:00:00", assignee="Al  Smith"),
               sample.action("Open", due="2026-10-02T00:00:00", assignee="Someone Else", assignee_id=9),
               sample.action("Open", due="2026-10-03T00:00:00", assignee="Nobody KNOWN")]
    listed = metrics.build_open_actions(actions, sample.TODAY, people)
    assert [a["contractor"] for a in listed] == ["New Co", "Id Co", "–"]


def test_open_incidents_are_open_events_most_overdue_first(report):
    assert report["open_incidents"] == {"total": 1, "rows": [{
        "event": "6", "date": "20 Sep 2026", "type": "Near Miss", "workgroup": "CPO - MLG",
        "step": "Assess the Event", "actionee": "Otto owner", "contractor": "Acme Haulage", "due": "5 Oct 2026",
        "status": "Overdue 6 days", "overdue": True}]}


def test_open_incidents_keep_the_most_overdue_and_leave_out_other_sites():
    events = [sample.event(n, "2026-09-01", "CPO - Ozland", "Near Miss", status="Open Workflow",
                           target=f"2026-10-{n:02d}T00:00:00") for n in range(1, 21)]
    events += [sample.event(30, "2026-09-01", "CPO - Ozland", "Near Miss", status="Open Workflow"),
               sample.event(31, "2026-09-01", "PER - Management", "Near Miss", status="Open Workflow",
                            target="2026-01-01T00:00:00"),
               sample.event(32, "2026-09-01", "CPO - Ozland", "Near Miss",
                            target="2026-01-01T00:00:00")]
    listed = metrics.build_open_incidents(events, [], sample.TODAY, keep=15)
    assert listed["total"] == 21
    assert [e["event"] for e in listed["rows"]] == [str(n) for n in range(1, 16)]
    assert listed["rows"][0]["status"] == "Overdue 10 days" and listed["rows"][0]["contractor"] == "–"
    assert listed["rows"][10]["status"] == "Due today"
    assert listed["rows"][0]["actionee"] == sample.FAKE_NAME
    every = metrics.build_open_incidents(events, [], sample.TODAY, keep=50)
    assert every["rows"][-1]["event"] == "30" and every["rows"][-1]["status"] == "No target date"


def test_ozland_ert_obligation_day_by_day(report):
    from datetime import date
    oz = report["ozland_ert"]
    assert oz["fy_start"] == date(2026, 7, 1)
    assert [(d["label"], d["day_shift"], d["night_shift"], d["met"]) for d in oz["days"]] == [
        ("8 Oct 2026", 2, 1, False),      # 604 not qualified until HAZMAT on 10 Oct
        ("10 Oct 2026", 2, 2, True),      # a duplicate roster row counts once
        ("11 Oct 2026", 1, 2, False),     # RR, NMG staff and a 5-of-6 member do not count
    ]
    assert (oz["met"], oz["missed"]) == (1, 2)


def test_expired_competency_stops_counting():
    people = [sample.person("CPO - Ozland", employer="Ozland Drill and Blast", pid=1,
                            roles=("ERT Member",))]
    comps = ([sample.competency("E1", name) for name in sample.ALL_SIX[1:]]
             + [sample.competency("E1", sample.ALL_SIX[0], expires="2026-10-09T00:00:00")])
    roster = [sample.rostered(1, "2026-10-08", sample.DAY), sample.rostered(1, "2026-10-09", sample.DAY)]
    oz = metrics.build_ozland_ert(people, roster, sample.SHIFT_TYPES, comps, sample.TODAY)
    assert [d["day_shift"] for d in oz["days"]] == [1, 0]
    empty = metrics.build_ozland_ert([], [], [], [], sample.TODAY)
    assert empty["days"] == [] and empty["met"] == 0


def test_near_miss_and_hazard_reporting():
    report = metrics.build_report(sample.RAW, sample.TODAY, "x")["reporting"]
    assert report["labels"][-1] == "Oct 26" and len(report["labels"]) == 12    # runs to today
    assert report["to_date"] == "11 Oct 2026"
    assert list(report["series"]) == [config.MINING, config.EXPLORATION]
    mining, exploration = (dict(report["series"][b]) for b in (config.MINING, config.EXPLORATION))
    assert list(mining) == ["Near misses", "Hazard reports"]
    assert mining["Hazard reports"][-4:] == [1, 0, 2, 1]  # Jul to Oct: discarded and Perth left out
    assert exploration["Hazard reports"][-4:] == [0, 1, 0, 0]
    assert sum(mining["Near misses"]) == 2 and sum(exploration["Near misses"]) == 0
    table = {row["label"]: row["cells"] for row in report["table"]}
    assert report["columns"] == ["Jul", "Aug", "Sep", "Oct", "FYTD"]   # every month from 1 July to today
    assert table["Near misses"] == ["–", "–", "2", "–", "2", "–", "–", "–", "–", "–"]
    assert table["Hazard reports"] == ["1", "–", "2", "1", "4", "–", "1", "–", "–", "1"]


def test_reports_by_company_follow_the_reporter():
    people = [sample.person("CPO - Ozland", employer="Ozland Drill and Blast", pid=7, first="Oz", last="DRILLER"),
              sample.person("CPO - Geology", pid=8, first="Nina", last="NMG")]
    events = [sample.event(1, "2026-09-03", "CPO - Ozland", "Near Miss", "Near Miss (Other)"),
              sample.event(2, "2026-08-03", "CPO - Ozland", "Near Miss", "Near Miss (Other)"),
              sample.event(3, "2026-06-03", "CPO - Ozland", "Near Miss", "Near Miss (Other)")]   # last FY
    events[0]["reportedBy"] = "Oz  driller"
    events[1]["reportedBy"] = "Somebody GONE"
    checklists = [dict(sample.hazard("2026-07-10"), userId=8), dict(sample.hazard("2026-09-10"), userId=8),
                  dict(sample.hazard("2026-09-12", workgroup="CPO - Ozland"), userId=7)]
    raw = dict(sample.RAW, events=events, checklists=checklists, people=people)
    rows = metrics.build_report(raw, sample.TODAY, "x")["reporting"]["by_company"]
    assert [group["company"] for group in rows] == [
        "New Murchison Gold Ltd", "Ozland Drill and Blast", config.UNKNOWN_COMPANY]
    assert rows[0]["rows"] == [("Near misses", ["–"] * 5), ("Hazard reports", ["1", "–", "1", "–", "2"])]
    assert rows[1]["rows"] == [("Near misses", ["–", "–", "1", "–", "1"]), ("Hazard reports", ["–", "–", "1", "–", "1"])]
    assert rows[2]["rows"] == [("Near misses", ["–", "1", "–", "–", "1"]), ("Hazard reports", ["–"] * 5)]


def test_open_incident_actionee_is_whoever_holds_the_step():
    waiting = sample.event(1, "2026-09-01", "CPO - Ozland", "Near Miss", status="Open Workflow",
                           reported_to="Sue  SUPERVISOR ", step="Initiator to add information")
    waiting["reportedBy"] = "Ian  INITIATOR"
    assessing = sample.event(2, "2026-09-01", "CPO - Ozland", "Near Miss", status="Open Workflow",
                             reported_to="Sue  SUPERVISOR ", step="Assess the Event")
    nobody = sample.event(3, "2026-09-01", "CPO - Ozland", "Near Miss", status="Open Workflow",
                          reported_to=None, step="Assess the Event")
    rows = metrics.build_open_incidents([waiting, assessing, nobody], [], sample.TODAY)["rows"]
    assert {r["event"]: r["actionee"] for r in rows} == {
        "1": "Ian INITIATOR", "2": "Sue SUPERVISOR", "3": "Unassigned"}


def test_close_out_counts_overdue_against_closed_by_the_due_date():
    from datetime import date
    people = [sample.person("CPO - Ozland", employer="Ozland Drill and Blast", first="Oz", last="BOSS"),
              sample.person("CPO - Geology", first="Nina", last="NMG"),
              sample.person("CPO - MLG", employer="Acme Haulage", first="Al", last="ACME")]

    def ev(n, day, to, target, status="Closed and Saved"):
        return sample.event(n, day, "CPO - Ozland", "Near Miss", status=status, reported_to=to,
                            target=target and f"{target}T00:00:00")

    events = [ev(1, "2026-09-01", "Oz BOSS", "2026-09-10"),                     # closed on the day
              ev(2, "2026-09-01", "Oz  boss ", "2026-09-10"),                   # closed a day late
              ev(3, "2026-09-01", "Oz BOSS", "2026-10-01", "Open Workflow"),    # open, past target
              ev(4, "2026-10-01", "Oz BOSS", "2026-11-01", "Open Workflow"),    # open, not yet due
              ev(5, "2026-09-01", "Oz BOSS", None),                             # no target
              ev(6, "2026-09-01", "Oz BOSS", "2026-09-10"),                     # closed, no close date
              ev(7, "2025-10-11", "Oz BOSS", "2025-10-12"),                     # 12 months + 1 day ago
              ev(8, "2026-09-01", "Nina NMG", "2026-09-30"),
              ev(9, "2026-09-01", "Al ACME", "2026-09-30"),                     # another company
              ev(10, "2026-09-01", "Gone PERSON", "2026-09-30")]                # not in PeopleTray
    closed = {"1": date(2026, 9, 10), "2": date(2026, 9, 11), "7": date(2025, 10, 20),
              "8": date(2026, 9, 2), "9": date(2026, 10, 9), "10": date(2026, 10, 9)}
    out = metrics.build_close_out(events, people, closed, sample.TODAY)
    assert out["companies"]["Ozland Drill and Blast"] == {
        "on_time": 1, "late": 1, "open_overdue": 1, "not_due": 1, "no_target": 2}
    assert out["companies"]["NMG"] == {"on_time": 1, "late": 0, "open_overdue": 0, "not_due": 0,
                                       "no_target": 0}
    assert out["unmatched"] == 1 and out["since"] == "12 Oct 2025"
    assert metrics.build_close_out(events, people, None, sample.TODAY) is None


def test_close_out_needs_the_web_app_close_dates(report):
    assert report["close_out"] is None
    with_web = metrics.build_report(dict(sample.RAW, web_charts=dict(WEB, closed_events={})),
                                    sample.TODAY, "x")
    assert set(with_web["close_out"]["companies"]) == {"NMG", "Ozland Drill and Blast"}


def test_nmg_and_ozland_always_have_a_row_in_reports_by_company():
    raw = dict(sample.RAW, events=[], checklists=[])
    rows = metrics.build_report(raw, sample.TODAY, "x")["reporting"]["by_company"]
    assert [group["company"] for group in rows] == ["New Murchison Gold Ltd", "Ozland Drill and Blast"]
    assert all(cells == ["–"] * 5 for group in rows for _, cells in group["rows"])
