import generate_dashboard
from tests import sample


def test_build_writes_the_page(tmp_path):
    out = tmp_path / "docs" / "index.html"
    report = generate_dashboard.build(sample.RAW, sample.TODAY, "11 Oct 2026, 18:30 AWST", out)
    page = out.read_text(encoding="utf-8")
    assert report["month_label"] == "September 2026"
    assert page.startswith("<!doctype html>")
    assert "September 2026" in page
    assert "data:image/png;base64," in page       # the committed logo is embedded
    assert "Quixote" not in page
