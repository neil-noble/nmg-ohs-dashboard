"""Build docs/index.html from live PeopleTray data."""
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

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


def warnings(report, web_error=None):
    """One line for everything the figures leave out, for the workflow log."""
    lines = []
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
    report = build(raw, today, periods.now_label())
    print(f"Built {OUTPUT} for {report['month_label']} (charts from {report['charts_source']})")
    for line in warnings(report, raw["web_error"]):
        print(f"::warning::{line}")


if __name__ == "__main__":
    if sys.argv[1:] == ["--web-cache-fresh"]:
        # For the workflow: skip the browser install when the cache will be used.
        fresh = load_web_cache(os.environ.get("WEB_CACHE", ""), datetime.now(timezone.utc))
        print("true" if fresh else "false")
    else:
        main()
