"""Build docs/index.html from live PeopleTray data."""
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import eomhours
import fetch
import metrics
import periods
import render
import webcharts

ROOT = Path(__file__).parent
OUTPUT = ROOT / "docs" / "index.html"
OZLAND_NAME = "ozland.html"          # read by the ERT dashboard; published beside index.html
# The page rebuilds every 5 minutes, but it signs in to PeopleTray's web app as Neil at most once
# every 30 (2026-10-22): in between, the last sign-in's figures are reused from this cache.
WEB_CACHE_AGE = timedelta(minutes=30)
# A missing month's End of Month Report hours are worked out again at most every 6 hours, so late
# roster edits still reach the page (the report is a big download).
EOM_CACHE_AGE = timedelta(hours=6)
EOM_CACHE_NAME = "eomhours.json"


def build(raw, today, generated, out_path=OUTPUT):
    report = metrics.build_report(raw, today, generated)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render.render(report), encoding="utf-8")
    (out_path.parent / OZLAND_NAME).write_text(render.render_ozland(report), encoding="utf-8")
    return report


def _cache_dump(charts, now):
    return json.dumps({"fetched_at": now.isoformat(),
                       "sheq_actions": charts["sheq_actions"], "open_workflows": charts["open_workflows"],
                       "closed_events": {k: v.isoformat() for k, v in charts.get("closed_events", {}).items()}})


def load_web_cache(path, now, max_age=WEB_CACHE_AGE):
    """The cached web figures when they are younger than max_age, otherwise None."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if now - datetime.fromisoformat(data["fetched_at"]) >= max_age:
            return None
        return {"sheq_actions": [tuple(x) for x in data["sheq_actions"]],
                "open_workflows": [tuple(x) for x in data["open_workflows"]],
                "closed_events": {k: date.fromisoformat(v) for k, v in data["closed_events"].items()}}
    except (OSError, ValueError, KeyError, TypeError):
        return None


def read_web_charts(fetcher=webcharts.fetch_web_charts, cache=None, now=None):
    """(charts, error). A failed sign-in must not stop the dashboard: it falls back to the API.
    With a cache path, fresh cached figures are used instead of signing in, and a successful
    sign-in refreshes the cache."""
    now = now or datetime.now(timezone.utc)
    if cache:
        cached = load_web_cache(cache, now)
        if cached:
            return cached, None
    try:
        charts = fetcher()
    except webcharts.WebChartsError as error:
        return None, str(error)
    if cache and charts:
        Path(cache).parent.mkdir(parents=True, exist_ok=True)
        Path(cache).write_text(_cache_dump(charts, now), encoding="utf-8")
    return charts, None


def _eom_cache_path(web_cache):
    return Path(web_cache).parent / EOM_CACHE_NAME if web_cache else None


def load_eom_cache(path, now, month, max_age=EOM_CACHE_AGE):
    """The cached End of Month Report hours, when fresh and worked out in this reporting month."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if now - datetime.fromisoformat(data["fetched_at"]) >= max_age or data["month"] != list(month):
            return None
        return {tuple(int(x) for x in key.split("-")): value for key, value in data["hours"].items()}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


def read_eom_hours(raw, today, cache=None, now=None, fetcher=eomhours.fetch_eom_hours, env=os.environ):
    """(hours by month, error) for finished months the exposure hours feed lacks. A failure
    leaves the rates where the feed puts them, and says so in the log."""
    now = now or datetime.now(timezone.utc)
    month = periods.reporting_month(today)
    feed = metrics.normalise_hours(raw["hours"], metrics.new_issues())
    for ym, record in (raw.get("eom_history") or {}).items():     # sent months need no download
        for area, value in record["hours"].items():
            feed[(area, ym)] = value
    wanted = eomhours.missing_months(feed, month)
    if cache:
        cached = load_eom_cache(cache, now, month)
        if cached is not None and set(wanted) <= set(cached):
            return {m: cached[m] for m in wanted}, None
    try:
        found = fetcher(wanted, raw.get("shifttypes", []), env)
    except eomhours.EomHoursError as error:
        return {}, str(error)
    if cache and (found or not wanted):
        Path(cache).parent.mkdir(parents=True, exist_ok=True)
        Path(cache).write_text(json.dumps({
            "fetched_at": now.isoformat(), "month": list(month),
            "hours": {f"{y}-{m:02d}": v for (y, m), v in found.items()}}), encoding="utf-8")
    return found, None


def load_eom_history(path):
    """(months the EOM report has sent, error): {(year, month): {"hours": {area: h},
    "injuries": {area: {"recordable": n, "lti": n}}}} from the NMG EOM project's
    data/history.yaml. Without it the rates fall back to PeopleTray's own figures."""
    if not path:
        return {}, None
    try:
        import yaml

        months = yaml.safe_load(Path(path).read_text(encoding="utf-8"))["months"]
        out = {}
        for key, record in months.items():
            year, month = (int(x) for x in str(key).split("-"))
            out[(year, month)] = {"hours": {a: float(h) for a, h in record["hours"].items()},
                                  "injuries": {a: {k: int(v) for k, v in i.items()}
                                               for a, i in (record.get("injuries") or {}).items()},
                                  "points": {a: (float(p["trifr"][a]), float(p["ltifr"][a]))
                                             for p in [record.get("points") or {}]
                                             for a in (p.get("trifr") or {}) if a in (p.get("ltifr") or {})}}
        return out, None
    except Exception as error:   # a missing or changed file must not stop the dashboard
        return {}, f"EOM history not read ({type(error).__name__})"


def warnings(report, web_error=None, eom_error=None):
    """One line for everything the figures leave out, for the workflow log."""
    lines = []
    if eom_error:
        lines.append(f"End of Month Report hours not read ({eom_error}); the rates stay at the "
                     "last month in the exposure hours feed")
    if web_error:
        lines.append(f"PeopleTray web charts not read ({web_error}); SHEQ Actions and Open "
                     "Workflows are showing API figures")
    if report["unmapped"]:
        names = ", ".join(" ".join(name.split()) for name in report["unmapped"])
        lines.append(f"Unmapped workgroups left out of the figures: {names}")
    if report["undated"]:
        lines.append(f"{report['undated']} events have no date and were not counted")
    if report["unclassified"]:
        lines.append(f"{report['unclassified']} injuries have no injury type or recognised "
                     "sub-type; they are not in TRIFR or LTIFR")
    return lines


def main():
    today = periods.today_perth()
    raw = fetch.fetch_all(today)
    raw["web_charts"], raw["web_error"] = read_web_charts(cache=os.environ.get("WEB_CACHE"))
    raw["eom_history"], history_error = load_eom_history(os.environ.get("EOM_HISTORY"))
    if history_error:
        print(f"::warning::{history_error}; the rates use PeopleTray's own hours and injuries")
    raw["eom_hours"], eom_error = read_eom_hours(raw, today, cache=_eom_cache_path(os.environ.get("WEB_CACHE")))
    report = build(raw, today, periods.now_label())
    print(f"Built {OUTPUT} for {report['month_label']} (charts from {report['charts_source']})")
    for ym, areas in sorted(raw["eom_hours"].items()):
        print(f"{ym[0]}-{ym[1]:02d} hours from the End of Month Report: "
              + ", ".join(f"{b} {round(areas[b]):,}" for b in sorted(areas)))
    for line in warnings(report, raw["web_error"], eom_error):
        print(f"::warning::{line}")


if __name__ == "__main__":
    if sys.argv[1:] == ["--web-cache-fresh"]:
        # For the workflow: skip the browser install when the cache will be used.
        now, cache = datetime.now(timezone.utc), os.environ.get("WEB_CACHE", "")
        fresh = load_web_cache(cache, now) and load_eom_cache(
            _eom_cache_path(cache) or "", now, periods.reporting_month(periods.today_perth())) is not None
        print("true" if fresh else "false")
    else:
        main()
