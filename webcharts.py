"""Read the two charts on PeopleTray's SHEQ home page.

The "SHEQ Actions" and "Open Workflows" charts there count things the API does not return
(forms issued but not yet submitted, and PeopleTray's own scoping of actions), so the only
way to show the same numbers is to sign in to the web app and read them off the page. Both
charts are fed by JSON written into the page itself. Nothing is kept between runs.
"""
import json
import os

LOGIN_URL = "https://au.peopletray.com/Common/Account/Login"
SHEQ_HOME_URL = "https://au.peopletray.com/SheTray/Home"
ACTIONS_MODEL = "workflowActionsChartModel"
WORKFLOWS_MODEL = "openWorkflowsPieChartModel"
ACTION_BARS = ("Assigned", "Due", "Overdue")


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


def read_sheq_home(username, password):
    """Sign in and return the SHEQ home page's HTML. Same sign-in as the Evacuation List project."""
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
            return response.text()
        finally:
            browser.close()


def fetch_web_charts(env=os.environ, reader=read_sheq_home):
    """The two charts, or None when no web login is configured.

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
    return parse_sheq_home(html)
