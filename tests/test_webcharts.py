import json
from datetime import date

import pytest

import webcharts

# Shaped like the two inline models on PeopleTray's SHEQ home page (/SheTray/Home).
SHEQ_HOME = """
<html><body><h4>SHEQ Actions</h4><script type="text/javascript">
    $(document).ready(function () {
        var workflowActionsChartModel = {"Series":[{"name":"Assigned","peopleCount":0,"description":null,"y":5,"color":"#CCCCCC"},{"name":"Due","peopleCount":0,"description":null,"y":1,"color":"#00B512"},{"name":"Overdue","peopleCount":0,"description":null,"y":3,"color":"#df4b33"}],"Categories":[],"Message":null,"UserId":0};
        renderWorkflowActionsChart(workflowActionsChartModel);
    });
</script><h4>Open Workflows</h4><script type="text/javascript">
    $(document).ready(function () {
        var openWorkflowsPieChartModel = {"Series":[{"name":"CCV - Electrical Energy ","color":null,"y":1,"isLeaf":false,"id":0},{"name":"Exploration Monthly LV Inspection\\t\\t","color":null,"y":2,"isLeaf":false,"id":0},{"name":"Safety Events","color":null,"y":17,"isLeaf":false,"id":0},{"name":"Light Vehicle Prestarts","color":null,"y":107,"isLeaf":false,"id":0},{"name":"Nothing open; {odd} name","color":null,"y":0,"isLeaf":false,"id":0}],"Message":null,"UserId":0};
        renderOpenWorkflowsPieChartModel(openWorkflowsPieChartModel);
    });
</script></body></html>
"""
# Shaped like the Safety Events search's data feed, closed events only (trimmed).
CLOSED = json.dumps({"sEcho": 1, "iTotalRecords": 3, "aaData": [
    {"EntityId": 30803, "TransitionDate": "/Date(1791412086050)/", "EventCloseDate": "/Date(1793923200000)/"},
    {"EntityId": 30722, "TransitionDate": "/Date(1791180724950)/", "EventCloseDate": "/Date(1791158400000)/"},
    {"EntityId": 1, "TransitionDate": "/Date(-62135596800000)/"}]})
LOGIN_PAGE = "<html><head><title>PeopleTray Sign In</title></head><body><form id='login'></form></body></html>"


def test_parse_reads_both_charts():
    charts = webcharts.parse_sheq_home(SHEQ_HOME)
    assert charts["sheq_actions"] == [("Assigned", 5), ("Due", 1), ("Overdue", 3)]
    assert charts["open_workflows"] == [
        ("CCV - Electrical Energy", 1), ("Exploration Monthly LV Inspection", 2),
        ("Safety Events", 17), ("Light Vehicle Prestarts", 107), ("Nothing open; {odd} name", 0)]


def test_parse_rejects_a_page_without_the_charts():
    with pytest.raises(webcharts.WebChartsError, match="workflowActionsChartModel"):
        webcharts.parse_sheq_home(LOGIN_PAGE)


def test_parse_rejects_a_chart_missing_a_bar():
    broken = SHEQ_HOME.replace('{"name":"Due","peopleCount":0,"description":null,"y":1,"color":"#00B512"},', "")
    with pytest.raises(webcharts.WebChartsError, match="Assigned, Due, Overdue"):
        webcharts.parse_sheq_home(broken)


def test_no_credentials_means_no_web_charts():
    def reader(username, password):
        raise AssertionError("must not sign in without credentials")

    assert webcharts.fetch_web_charts({}, reader) is None
    assert webcharts.fetch_web_charts({"PT_WEB_USERNAME": "neil", "PT_WEB_PASSWORD": ""}, reader) is None


def test_credentials_are_passed_to_the_reader():
    seen = []

    def reader(username, password):
        seen.append((username, password))
        return SHEQ_HOME, CLOSED

    charts = webcharts.fetch_web_charts({"PT_WEB_USERNAME": "neil", "PT_WEB_PASSWORD": "s3cret"}, reader)
    assert seen == [("neil", "s3cret")]
    assert charts["sheq_actions"][2] == ("Overdue", 3)
    assert charts["closed_events"] == {"30803": date(2026, 10, 8), "30722": date(2026, 10, 5)}


def test_closed_events_are_dated_in_perth_and_placeholders_dropped():
    # 1791180724950 ms is 4 Oct 2026 23:32 UTC, which is 5 Oct in Perth.
    assert webcharts.parse_closed_events(CLOSED) == {"30803": date(2026, 10, 8), "30722": date(2026, 10, 5)}


def test_a_closed_events_feed_that_is_not_json_is_an_error():
    with pytest.raises(webcharts.WebChartsError, match="closed safety events"):
        webcharts.parse_closed_events("<html>sign in</html>")


def test_any_reader_failure_becomes_a_web_charts_error_without_the_password():
    def reader(username, password):
        raise RuntimeError(f"browser crashed while typing {password}")

    with pytest.raises(webcharts.WebChartsError) as caught:
        webcharts.fetch_web_charts({"PT_WEB_USERNAME": "neil", "PT_WEB_PASSWORD": "s3cret"}, reader)
    assert "s3cret" not in str(caught.value)
    assert "RuntimeError" in str(caught.value)
