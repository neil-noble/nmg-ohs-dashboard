"""Person hours for a finished month that PeopleTray's exposure hours feed does not have yet.

The exposure hours feed is filled in by hand some time after the month ends, but the NMG EOM
report (C:\\claude\\NMG EOM, sent on the 1st) already works the month's hours out from the web
app's End of Month Report. Neil, 2026-11-07: put the latest figures on the dashboard. So a
finished month that is missing from the feed takes its hours from that report, by the EOM
project's rules (copied from its eom/hours.py and eom/config.py; keep the two in step). As soon
as the feed has the month, the feed wins.
"""
import io
import re
from collections import defaultdict
from datetime import date, datetime, timedelta

import config
from periods import add_months

EXPORT_URL = "https://au.peopletray.com/Common/PeopleEOMReport/GetReport"
LOGIN_URL = "https://au.peopletray.com/Common/Account/Login"
MAX_DAYS = 31                 # the server cuts any longer request
MARGIN_DAYS = 21              # either side of the month, so a fly-in/fly-out swing is judged whole
MOST_MONTHS = 2               # never reach further back than this for missing months
COLUMNS = ("Date", "Employee Id", "First Name", "Last Name", "Employer", "Workgroup", "Shift Type",
           "Exp Hours")

# ── The EOM report's rules (Neil, 2026-10-28) ─────────────────────────────────
MINING, EXPLORATION = config.MINING, config.EXPLORATION
WORKGROUP_AREA = {
    "Contractors - Other": MINING, "CPO - Management - Contractors/Visitors": MINING,
    "CPO - MLG": MINING, "CPO - Ozland": MINING, "CPO - Administration": MINING, "CPO - BV": MINING,
    "CPO - Geology": MINING, "CPO - Health and Safety": MINING, "CPO - Management": MINING,
    "CPO - Project": MINING, "CPO - Tech Services": MINING,
    "Drilling Contractors": EXPLORATION, "GG - Exploration Contractors": EXPLORATION,
    "GG - Exploration": EXPLORATION,
}
PER_PREFIX = "PER - "
EXCLUDED_WORKGROUPS = ("Contractors - Local",)
FA_WORKGROUP = "Flight/Accommodation ONLY"
EXPLORATION_WORKGROUPS = ("GG - Exploration", "GG - Exploration Contractors", "Drilling Contractors")
MINING_CODES = frozenset({"DS", "DSX", "NS"})
TRAVEL_CODES = frozenset({"FIA", "FIP", "FOA", "FOP", "DIA", "DIP", "DOA", "DOP"})
FA_NOT_COUNTED = frozenset({"FIX", "FOX", "FAP", "RR"})
MEEKA_EMPLOYER = "Meeka Metals"
OZLAND_EMPLOYER = "Ozland Drill and Blast"
_PLACEHOLDER_LAST = re.compile(r"^BOOKING[-_ ]", re.IGNORECASE)


class EomHoursError(RuntimeError):
    """The End of Month Report could not be read. Never carries the password."""


def _text(value):
    return "" if value is None else str(value).strip()


def _is_exploration_code(code):
    return bool(code) and code.startswith("E")


def _is_work(code):
    return code in MINING_CODES or _is_exploration_code(code)


def _placeholder(first, last):
    return _text(first).lower() in ("dummy", "external") or bool(_PLACEHOLDER_LAST.match(_text(last)))


def _westgold(employer):
    return "westgold" in _text(employer).replace(" ", "").lower()


def _person(r):
    return r["Employee Id"] or f'{r["First Name"]} {r["Last Name"]}'


def _swing_is_all_mining(rows, codes):
    """Row index -> True when every work shift in that row's swing is a mining shift."""
    result, by_person = {}, defaultdict(list)
    for i, r in enumerate(rows):
        by_person[_person(r)].append(i)
    for indices in by_person.values():
        indices.sort(key=lambda i: rows[i]["_day"])
        swings, current, previous = [], [], None
        for i in indices:
            code = codes.get(rows[i]["Shift Type"]) or ""
            gap = previous is not None and (rows[i]["_day"] - previous).days > 1
            if current and (gap or (code in TRAVEL_CODES and code[1] == "I")):
                swings.append(current)
                current = []
            current.append(i)
            previous = rows[i]["_day"]
            if code in TRAVEL_CODES and code[1] == "O":
                swings.append(current)
                current = []
        if current:
            swings.append(current)
        for swing in swings:
            work = [codes.get(rows[i]["Shift Type"]) for i in swing
                    if _is_work(codes.get(rows[i]["Shift Type"]))]
            mining = bool(work) and all(code in MINING_CODES for code in work)
            for i in swing:
                result[i] = mining
    return result


def allocate(rows, codes, ym):
    """{"Mining": hours, "Exploration": hours} for month ym, by the EOM report's rules."""
    rows = [dict(r, _day=datetime.strptime(r["Date"], "%d-%b-%Y").date()) for r in rows]
    all_mining = _swing_is_all_mining(rows, codes)
    totals = {MINING: 0.0, EXPLORATION: 0.0}
    for i, r in enumerate(rows):
        workgroup, employer, hours = r["Workgroup"], r["Employer"], r["Exp Hours"]
        if _placeholder(r["First Name"], r["Last Name"]) or _westgold(employer):
            continue
        if (r["_day"].year, r["_day"].month) != tuple(ym) or workgroup in EXCLUDED_WORKGROUPS:
            continue
        code = codes.get(r["Shift Type"])
        if workgroup == FA_WORKGROUP:
            if employer == MEEKA_EMPLOYER:
                continue
            if employer == OZLAND_EMPLOYER or code in MINING_CODES:
                totals[MINING] += hours
            elif code in FA_NOT_COUNTED:
                continue
            elif _is_exploration_code(code):
                totals[EXPLORATION] += hours
            elif code in TRAVEL_CODES:
                totals[MINING if all_mining[i] else EXPLORATION] += hours
            continue
        if workgroup in EXPLORATION_WORKGROUPS:
            on_mining = code in MINING_CODES or (code in TRAVEL_CODES and all_mining[i])
            totals[MINING if on_mining else EXPLORATION] += hours
        elif workgroup in WORKGROUP_AREA:
            totals[WORKGROUP_AREA[workgroup]] += hours
        elif workgroup.startswith(PER_PREFIX):
            totals[MINING] += hours
    return totals


def read_rows(bodies):
    """The export's rows, from one or more downloaded workbooks."""
    import openpyxl

    out = []
    for body in bodies:
        wb = openpyxl.load_workbook(io.BytesIO(body), read_only=True, data_only=True)
        rows = wb.worksheets[0].iter_rows(values_only=True)
        header = [_text(h) for h in next(rows)]
        missing = [c for c in COLUMNS if c not in header]
        if missing:
            raise EomHoursError(f"End of Month Report is missing column(s): {', '.join(missing)}")
        for values in rows:
            r = dict(zip(header, values))
            if not r.get("Date"):
                continue
            rec = {c: _text(r.get(c)) for c in COLUMNS if c != "Exp Hours"}
            rec["Exp Hours"] = float(r.get("Exp Hours") or 0)
            out.append(rec)
        wb.close()
    return out


def missing_months(hours, month):
    """Finished months after the feed's latest month with hours, up to the month before `month`."""
    have = [m for (_, m), value in hours.items() if value]
    if not have:
        return []
    latest, last_done = max(have), add_months(month, -1)
    out = []
    candidate = add_months(latest, 1)
    while candidate <= last_done and len(out) < MOST_MONTHS:
        out.append(candidate)
        candidate = add_months(candidate, 1)
    return out


def _chunks(first, last):
    out, start = [], first
    while start <= last:
        end = min(start + timedelta(days=MAX_DAYS - 1), last)
        out.append((start, end))
        start = end + timedelta(days=1)
    return out


def _span(ym):
    first = date(ym[0], ym[1], 1)
    after = add_months(ym, 1)
    last = date(after[0], after[1], 1) - timedelta(days=1)
    return first - timedelta(days=MARGIN_DAYS), last + timedelta(days=MARGIN_DAYS)


def download(months, username, password):
    """The report's workbooks covering every month in `months`, margins included."""
    from playwright.sync_api import sync_playwright

    bodies = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            context = browser.new_context(timezone_id="Australia/Perth")
            page = context.new_page()
            page.set_default_timeout(60_000)
            page.goto(LOGIN_URL, wait_until="domcontentloaded")
            page.fill("#UserName", username)
            page.fill("#Password", password)
            page.click("#btnSubmit")
            page.wait_for_load_state("networkidle")
            if page.locator("#Password").count():
                raise EomHoursError("PeopleTray rejected the sign-in")
            first = min(_span(m)[0] for m in months)
            last = min(max(_span(m)[1] for m in months), date.today())
            for a, b in _chunks(first, last):
                url = (f"{EXPORT_URL}?fromDate={a:%d-%b-%Y}&toDate={b:%d-%b-%Y}"
                       "&sitePortId=&workgroupId=")
                response = context.request.get(url, timeout=300_000)
                body = response.body()
                if response.status != 200 or not body.startswith(b"PK"):
                    raise EomHoursError(f"End of Month Report {a:%d-%b-%Y}..{b:%d-%b-%Y} came back "
                                        f"HTTP {response.status}, not a workbook")
                bodies.append(body)
        finally:
            browser.close()
    return bodies


def fetch_eom_hours(months, shifttypes, env, downloader=download):
    """{(year, month): {"Mining": h, "Exploration": h}} for `months`, or {} with no web login."""
    username, password = env.get("PT_WEB_USERNAME", ""), env.get("PT_WEB_PASSWORD", "")
    if not months or not username or not password:
        return {}
    codes = {_text(s.get("statusName")): _text(s.get("statusCode"))
             for s in shifttypes if s.get("statusName")}
    try:
        rows = read_rows(downloader(months, username, password))
    except EomHoursError:
        raise
    except Exception as error:
        raise EomHoursError(f"could not read the End of Month Report: {type(error).__name__}") from None
    return {tuple(m): allocate(rows, codes, m) for m in months}
