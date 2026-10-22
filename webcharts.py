"""Read the two charts on PeopleTray's SHEQ home page, and when each safety event closed.

The "SHEQ Actions" and "Open Workflows" charts there count things the API does not return
(forms issued but not yet submitted, and PeopleTray's own scoping of actions), so the only
way to show the same numbers is to sign in to the web app and read them off the page. Both
charts are fed by JSON written into the page itself. The API has no close date for an event
either, so the web app's Safety Events search supplies that. Nothing is kept between runs.
"""
import json
import os
import re
import urllib.parse
from datetime import datetime, timedelta, timezone

LOGIN_URL = "https://au.peopletray.com/Common/Account/Login"
SHEQ_HOME_URL = "https://au.peopletray.com/SheTray/Home"
ACTIONS_MODEL = "workflowActionsChartModel"
WORKFLOWS_MODEL = "openWorkflowsPieChartModel"
ACTION_BARS = ("Assigned", "Due", "Overdue")
SAFETY_EVENT_TYPE = "7d320a3f-52c2-4bd7-8b96-93b2079f9a63"
SAFETY_EVENTS_URL = ("https://au.peopletray.com/Workflows/Search/GenericSearchContainer?workflowTypeId="
                     f"{SAFETY_EVENT_TYPE}&workflowClassificationId=1"
                     "&workflowProcessId=c2e8df5f-30d8-4414-b994-8d3ef5762c79"
                     "&name=Safety%20Event&menuName=Safety%20Events")
# The data request behind that page's table, as the page itself sends it, but for every closed
# event at once. Found 2026-10-22: TransitionDate is when an event entered its current step, so
# for a closed event it is the day it was closed. (EventCloseDate is the target close date.)
_COLUMNS = ("WorkflowInstanceId", "AccountCode", "Initiator", "EventTypeName", "Summary",
            "NumberOfActions", "LastCommentTruncated", "ActualRiskRatingCode", "PotentialRiskRatingCode")
CLOSED_EVENTS_URL = "https://au.peopletray.com/Workflows/Search/GetEventWorkflows?" + urllib.parse.urlencode(
    [("sEcho", "1"), ("iColumns", str(len(_COLUMNS))), ("sColumns", "," * (len(_COLUMNS) - 1)),
     ("iDisplayStart", "0"), ("iDisplayLength", "5000")]
    + [(f"mDataProp_{i}", name) for i, name in enumerate(_COLUMNS)]
    + [("WorkflowTypeId", SAFETY_EVENT_TYPE), ("ShowIncidents", "false"), ("FromDate", ""),
       ("ToDate", ""), ("ClosedWorkflowsOnly", "true"), ("OpenWorkflowsOnly", "false"),
       ("AllWorkflows", "false"), ("ReportedByPersonId", ""), ("EventTypeId", ""),
       ("EventDescription", ""), ("WorkflowNumber", ""), ("EventSubTypeId", ""),
       ("EventSeverityId", ""), ("WorkflowProcessStepId", "-1"), ("EventLocationId", ""),
       ("PotentialLikelihoodId", ""), ("PotentialConsequenceId", ""), ("PotentialRiskRatingId", ""),
       ("PotentialLikelihoodThisLevelOnly", "false"), ("PotentialConsequenceThisLevelOnly", "false"),
       ("IsMemberOfAnyApproverGroup", "False"), ("CustomFieldParameters", "[]"),
       ("WorkgroupFilterParameters", "{}")])
PERTH = timezone(timedelta(hours=8))


class WebChartsError(RuntimeError):
    """PeopleTray's web app did not hand over the charts."""


def _model(html, name):
    marker = f"var {name} = "
    start = html.find(marker)
    if start < 0:
        raise WebChartsError(f"{name} is not on the page (not signed in, or PeopleTray changed the page)")
    try:
        # raw_decode reads exactly one JSON value, so names containing ; or } cannot cut it short.
        model, _ = json.JSONDecoder().raw_decode(html, start + len(marker))
        return [(" ".join(str(point["name"]).split()), int(point["y"])) for point in model["Series"]]
    except (ValueError, KeyError, TypeError) as error:
        raise WebChartsError(f"{name} could not be read: {type(error).__name__}") from None


def parse_sheq_home(html):
    actions = dict(_model(html, ACTIONS_MODEL))
    if any(bar not in actions for bar in ACTION_BARS):
        raise WebChartsError(f"SHEQ Actions chart does not have {', '.join(ACTION_BARS)}")
    return {"sheq_actions": [(bar, actions[bar]) for bar in ACTION_BARS],
            "open_workflows": _model(html, WORKFLOWS_MODEL)}


def _ms_date(value):
    """A .NET "/Date(1791412086050)/" as a Perth date; None for blank or the year-1 placeholder."""
    found = re.search(r"-?\d+", value or "")
    if not found or int(found.group()) < 0:
        return None
    return (datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(milliseconds=int(found.group()))
            ).astimezone(PERTH).date()


def parse_closed_events(text):
    """{event id: the date it was closed} from the Safety Events search's closed-only feed."""
    try:
        rows = json.loads(text)["aaData"]
        closed = {str(row["EntityId"]): _ms_date(row.get("TransitionDate")) for row in rows}
    except (ValueError, KeyError, TypeError) as error:
        raise WebChartsError(f"closed safety events could not be read: {type(error).__name__}") from None
    return {event: day for event, day in closed.items() if day}


def read_sheq_home(username, password):
    """Sign in and return (the SHEQ home page's HTML, the closed safety events feed's JSON).
    Same sign-in as the Evacuation List project."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_context(timezone_id="Australia/Perth").new_page()
            page.set_default_timeout(60_000)
            page.goto(LOGIN_URL, wait_until="domcontentloaded")
            page.fill("#UserName", username)
            page.fill("#Password", password)
            page.click("#btnSubmit")
            page.wait_for_load_state("networkidle")
            if "/account/login" in page.url.lower():
                raise WebChartsError("PeopleTray rejected the sign-in (wrong password, locked account, "
                                     "or an MFA prompt)")
            response = page.goto(SHEQ_HOME_URL, wait_until="domcontentloaded")
            if "/account/login" in page.url.lower():
                raise WebChartsError("PeopleTray sent the SHEQ home page back to the sign-in screen")
            home = response.text()
            # Open the search page first, as a person would, then ask for its data.
            page.goto(SAFETY_EVENTS_URL, wait_until="domcontentloaded")
            closed = page.request.get(CLOSED_EVENTS_URL)
            if not closed.ok:
                raise WebChartsError(f"the closed safety events request failed ({closed.status})")
            return home, closed.text()
        finally:
            browser.close()


def fetch_web_charts(env=os.environ, reader=read_sheq_home):
    """The two charts and the closed events' dates, or None when no web login is configured.

    Raises WebChartsError for every failure, with a message that never includes the password.
    """
    username, password = env.get("PT_WEB_USERNAME", ""), env.get("PT_WEB_PASSWORD", "")
    if not username or not password:
        return None
    try:
        html = reader(username, password)
    except WebChartsError:
        raise
    except Exception as error:
        raise WebChartsError(f"could not read the SHEQ home page: {type(error).__name__}") from None
    html, closed = html
    return {**parse_sheq_home(html), "closed_events": parse_closed_events(closed)}
