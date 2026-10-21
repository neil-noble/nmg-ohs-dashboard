"""Build docs/index.html from live PeopleTray data."""
from pathlib import Path

import fetch
import metrics
import periods
import render
import webcharts

ROOT = Path(__file__).parent
OUTPUT = ROOT / "docs" / "index.html"
OZLAND_NAME = "ozland.html"          # read by the ERT dashboard; published beside index.html


def build(raw, today, generated, out_path=OUTPUT):
    report = metrics.build_report(raw, today, generated)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render.render(report), encoding="utf-8")
    (out_path.parent / OZLAND_NAME).write_text(render.render_ozland(report), encoding="utf-8")
    return report


def read_web_charts(fetcher=webcharts.fetch_web_charts):
    """(charts, error). A failed sign-in must not stop the dashboard: it falls back to the API."""
    try:
        return fetcher(), None
    except webcharts.WebChartsError as error:
        return None, str(error)


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
    raw["web_charts"], raw["web_error"] = read_web_charts()
    report = build(raw, today, periods.now_label())
    print(f"Built {OUTPUT} for {report['month_label']} (charts from {report['charts_source']})")
    for line in warnings(report, raw["web_error"]):
        print(f"::warning::{line}")


if __name__ == "__main__":
    main()
