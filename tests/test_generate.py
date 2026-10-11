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
