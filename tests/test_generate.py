import generate_dashboard
from tests import sample


def test_build_writes_the_page(tmp_path):
    out = tmp_path / "docs" / "index.html"
    report = generate_dashboard.build(sample.RAW, sample.TODAY, "11 Oct 2026, 18:30 AWST", out)
    page = out.read_text(encoding="utf-8")
    assert report["month_label"] == "September 2026"
    assert page.startswith("<!doctype html>")
    assert "September 2026" in page
    assert "<img" not in page
    assert "Quixote" not in page


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


def test_read_ert_dials_never_raises():
    import ertdials

    def broken():
        raise ertdials.ErtDialsError("the day shift dials are not on the ERT page")
    assert generate_dashboard.read_ert_dials(broken) == (None, "the day shift dials are not on the ERT page")
    assert generate_dashboard.read_ert_dials(lambda: {"rows": []}) == ({"rows": []}, None)


def test_warnings_report_an_unread_ert_dashboard():
    report = {"unmapped": [], "undated": 0, "unclassified": 0, "ert_error": "timed out"}
    lines = generate_dashboard.warnings(report)
    assert len(lines) == 1 and "timed out" in lines[0] and "Emergency Services" in lines[0]
