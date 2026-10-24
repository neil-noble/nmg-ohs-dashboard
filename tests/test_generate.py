import generate_dashboard
from tests import sample


def test_build_writes_the_page(tmp_path):
    out = tmp_path / "docs" / "index.html"
    report = generate_dashboard.build(sample.RAW, sample.TODAY, "11 Oct 2026, 18:30 AWST", out)
    page = out.read_text(encoding="utf-8")
    assert report["month_label"] == "October 2026"
    assert page.startswith("<!doctype html>")
    assert "October 2026 (to 11 Oct 2026)" in page
    assert "<img" not in page
    assert "Quixote" not in page
    assert 'id="ozland-ert"' in (out.parent / "ozland.html").read_text(encoding="utf-8")


def test_warnings_cover_everything_left_out_of_the_figures():
    report = {"unmapped": ["Shutdown Crew"], "undated": 2, "unclassified": 1}
    lines = generate_dashboard.warnings(report)
    assert len(lines) == 3
    assert "Shutdown Crew" in lines[0] and "2 events" in lines[1] and "1 injur" in lines[2]
    assert generate_dashboard.warnings({"unmapped": [], "undated": 0, "unclassified": 0}) == []


def test_warnings_report_a_failed_web_read():
    report = {"unmapped": [], "undated": 0, "unclassified": 0}
    lines = generate_dashboard.warnings(report, web_error="sign-in rejected")
    assert len(lines) == 1 and "sign-in rejected" in lines[0] and "API" in lines[0]


def test_read_web_charts_never_raises():
    import webcharts

    def broken(env=None):
        raise webcharts.WebChartsError("sign-in rejected")

    assert generate_dashboard.read_web_charts(broken) == (None, "sign-in rejected")
    assert generate_dashboard.read_web_charts(lambda env=None: None) == (None, None)
    charts = {"sheq_actions": [], "open_workflows": []}
    assert generate_dashboard.read_web_charts(lambda env=None: charts) == (charts, None)


def test_web_figures_are_reused_for_30_minutes(tmp_path):
    from datetime import date, datetime, timedelta, timezone
    cache = tmp_path / "web" / "web.json"
    start = datetime(2026, 10, 22, 8, 0, tzinfo=timezone.utc)
    charts = {"sheq_actions": [("Assigned", 5)], "open_workflows": [("Safety Events", 2)],
              "closed_events": {"30803": date(2026, 10, 8)}}
    calls = []

    def fetcher():
        calls.append(1)
        return charts

    assert generate_dashboard.read_web_charts(fetcher, cache, start) == (charts, None)
    later = generate_dashboard.read_web_charts(fetcher, cache, start + timedelta(minutes=29))
    assert later == (charts, None) and len(calls) == 1             # from the cache, no sign-in
    generate_dashboard.read_web_charts(fetcher, cache, start + timedelta(minutes=30))
    assert len(calls) == 2                                          # stale: signs in again
    assert generate_dashboard.load_web_cache(tmp_path / "missing.json", start) is None


def test_a_failed_sign_in_does_not_overwrite_the_cache(tmp_path):
    import webcharts
    from datetime import datetime, timedelta, timezone
    cache = tmp_path / "web.json"
    now = datetime(2026, 10, 22, 8, 0, tzinfo=timezone.utc)
    cache.write_text("not json", encoding="utf-8")

    def broken():
        raise webcharts.WebChartsError("sign-in rejected")

    assert generate_dashboard.read_web_charts(broken, cache, now) == (None, "sign-in rejected")
    assert cache.read_text(encoding="utf-8") == "not json"
