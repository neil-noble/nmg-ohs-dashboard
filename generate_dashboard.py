"""Build docs/index.html from live PeopleTray data."""
import base64
from pathlib import Path

import fetch
import metrics
import periods
import render

ROOT = Path(__file__).parent
LOGO = ROOT / "assets" / "nmg_logo.png"
OUTPUT = ROOT / "docs" / "index.html"


def build(raw, today, generated, out_path=OUTPUT):
    report = metrics.build_report(raw, today, generated)
    logo = base64.b64encode(LOGO.read_bytes()).decode("ascii") if LOGO.exists() else None
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render.render(report, logo), encoding="utf-8")
    return report


def warnings(report):
    """One line for everything the figures leave out, for the workflow log."""
    lines = []
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
    report = build(fetch.fetch_all(today), today, periods.now_label())
    print(f"Built {OUTPUT} for {report['month_label']}")
    for line in warnings(report):
        print(f"::warning::{line}")


if __name__ == "__main__":
    main()
