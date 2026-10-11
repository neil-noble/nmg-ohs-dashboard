import re

import pytest

import config
import metrics
import render
from tests import sample


@pytest.fixture(scope="module")
def report():
    return metrics.build_report(sample.RAW, sample.TODAY, "11 Oct 2026, 18:30 AWST")


@pytest.fixture(scope="module")
def page(report):
    return render.render(report, logo_b64="AAAA")


def test_is_a_complete_self_contained_document(page):
    assert page.startswith("<!doctype html>")
    assert page.rstrip().endswith("</html>")
    assert "<script" not in page
    assert not re.search(r'(src|href)="https?://', page)
    assert 'src="data:image/png;base64,AAAA"' in page


def test_every_section_is_present(page):
    for section in ("kpis", "event-table", "rate-trends", "event-trend", "event-mix",
                    "injury-classes", "injury-analysis", "status"):
        assert f'id="{section}"' in page


def test_header_shows_month_and_timestamp(page):
    assert "September 2026" in page
    assert "11 Oct 2026, 18:30 AWST" in page


def test_table_rows_and_cells(page):
    assert "<th>Mining</th>" not in page          # bucket headings span two columns
    assert re.search(r'colspan="2"[^>]*>Mining<', page)
    assert re.search(r'colspan="2"[^>]*>Exploration<', page)
    assert re.search(r"<th[^>]*>Total Person Hours Worked</th><td>30,500</td><td>90,500</td>"
                     r"<td>3,000</td><td>6,500</td>", page)
    assert re.search(r"<th[^>]*>Lost Time Injury Freq Rate \(LTIFR\)</th><td>NA</td><td>0.00</td>"
                     r"<td>NA</td><td>64.52</td>", page)


def test_kpi_tiles(page):
    assert page.count('class="v kpi"') == 5                # one card per measure, both buckets on it
    assert "Days since last LTI" in page and ">58<" in page
    assert ">64.52<" in page and ">30,500<" in page


def test_charts_are_inline_svg_with_month_labels(page):
    assert page.count("<svg") == 5                # TRIFR, LTIFR, event trend, two donuts
    assert ">Oct 25<" in page and ">Sep 26<" in page
    assert config.NAVY in page and config.GOLD in page
    assert "NaN" not in page and ">None<" not in page


def test_unmapped_notice_names_the_workgroup(page):
    assert 'id="notice"' in page
    assert "Shutdown Crew" in page


def test_no_notice_when_nothing_is_unmapped(report):
    clean = dict(report, unmapped=[], undated=0)
    assert 'id="notice"' not in render.render(clean)


def test_undated_events_are_mentioned(report):
    page = render.render(dict(report, unmapped=[], undated=2))
    assert 'id="notice"' in page and "2 events" in page


def test_no_personal_or_descriptive_data_reaches_the_page(page):
    for forbidden in ("Zebedee", "Quixote", "slipped", "Workshop bay", "replace the guard"):
        assert forbidden not in page


def test_peopletray_text_is_escaped():
    events = [sample.event(1, "2026-09-02", "CPO - Ozland", "Fire & <Explosion>")]
    raw = {"events": events, "injuries": [], "hours": [], "actions": [], "people": []}
    page = render.render(metrics.build_report(raw, sample.TODAY, "x"))
    assert "Fire &amp; &lt;Explosion&gt;" in page
    assert "<Explosion>" not in page


def test_empty_report_renders_without_a_logo():
    raw = {"events": [], "injuries": [], "hours": [], "actions": [], "people": []}
    page = render.render(metrics.build_report(raw, sample.TODAY, "x"))
    assert 'class="wordmark"' in page
    assert "No injuries recorded in the last 12 months" in page
    assert page.count("<svg") == 5
    assert "NaN" not in page and "nan%" not in page


def test_nice_axis_maximum():
    assert render.nice_max(0) == 5
    assert render.nice_max(4.2) == 5
    assert render.nice_max(22.52) == 25
    assert render.nice_max(64.52) == 100
    assert render.nice_max(7) == 10
    assert render.nice_max(130) == 250


def test_visuals_sit_on_a_report_canvas(page):
    assert 'class="canvas"' in page
    assert page.count('class="v') >= 14            # every visual is a card on the grid


def test_donuts_show_totals(page):
    assert re.search(r'class="donut-total"[^>]*>10<', page)      # 10 counted events in 12 months
    assert "Events by type" in page and "Event status" in page


def test_injury_classification_visual(page):
    assert "Injuries by classification" in page
    assert re.search(r'id="injury-classes".*First Aid Injury', page, re.S)


def test_line_charts_label_the_latest_value(page):
    assert page.count('class="dlabel"') >= 4      # last point of each series on both rate charts
