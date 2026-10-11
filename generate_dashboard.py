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


def main():
    today = periods.today_perth()
    report = build(fetch.fetch_all(today), today, periods.now_label())
    print(f"Built {OUTPUT} for {report['month_label']}")
    if report["unmapped"]:
        print(f"::warning::Unmapped workgroups left out of the figures: {', '.join(report['unmapped'])}")
    if report["undated"]:
        print(f"::warning::{report['undated']} events have no date and were not counted")


if __name__ == "__main__":
    main()
