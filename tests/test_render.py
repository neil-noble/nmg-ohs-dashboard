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
    return render.render(report)


def test_is_a_complete_self_contained_document(page):
    assert page.startswith("<!doctype html>")
    assert page.rstrip().endswith("</html>")
    assert "<script" not in page
    assert not re.search(r'(src|href)="https?://', page)
    assert "<img" not in page                      # no logo: the Wix page above already carries it


def test_every_section_is_present(page):
    for section in ("kpis", "event-table", "rate-trends", "event-trend", "event-mix",
                    "injury-classes", "injury-analysis", "status", "open-workflows",
                    "sheq-actions", "overdue-history"):
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
    assert page.count("<svg") == 7    # TRIFR, LTIFR, event trend, two donuts, workflow pie, action bars
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


def test_empty_report_renders():
    raw = {"events": [], "injuries": [], "hours": [], "actions": [], "people": []}
    page = render.render(metrics.build_report(raw, sample.TODAY, "x"))
    assert "No injuries recorded in the last 12 months" in page
    assert page.count("<svg") == 6                # no pie when nothing is open
    assert "No open workflows" in page and "No actions have gone overdue" in page
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


def test_events_by_month_is_a_line_chart(page):
    section = re.search(r'id="event-trend".*?</section>', page, re.S).group()
    assert section.count("<polyline") == len(config.TREND_GROUPS)     # one line per event type
    assert "<rect" not in section


def test_outstanding_actions_are_listed_with_their_actionee(page):
    section = re.search(r'id="open-actions".*?</section>', page, re.S).group()
    assert "Otto OWNER" in section and "Petra ACTIONEE" in section
    assert "Fit the &lt;new&gt; guard" in section and "<new>" not in section
    assert "Overdue 9 days" in section and "Due in 21 days" in section
    assert section.index("Otto OWNER") < section.index("Petra ACTIONEE")


def test_no_outstanding_actions_message(report):
    page = render.render(dict(report, open_actions=[]))
    assert "No outstanding actions" in page


def section_of(page, ident):
    return re.search(rf'id="{ident}".*?</section>', page, re.S).group()


def test_open_workflows_is_a_pie(page):
    section = section_of(page, "open-workflows")
    assert "<svg" in section and "Take 5" in section and "Safety Events" in section
    assert "Uniform Order" not in page and "Quixote" not in page
    assert "stroke-dasharray" not in section              # a filled pie, not a ring


def test_pie_with_several_slices_draws_one_wedge_each(report):
    page = render.render(dict(report, open_workflows=[("Injury", 5), ("Misfire", 3), ("A & B", 1)]))
    section = section_of(page, "open-workflows")
    assert section.count("<path") == 3
    assert "A &amp; B" in section


def test_sheq_actions_bar_graph_has_a_red_overdue_bar(page):
    section = section_of(page, "sheq-actions")
    assert section.count("<rect") == 3
    for label in ("Assigned", "Due", "Overdue"):
        assert f">{label}<" in section
    assert re.search(r'<rect[^>]*fill="#D94F32"[^>]*><title>Overdue: 1</title>', section)


def test_overdue_history_names_the_actionees(page):
    section = section_of(page, "overdue-history")
    assert "Otto OWNER" in section and "2 of 2" in section
    assert "Jul 2025" in section
    assert "Petra ACTIONEE" not in section                # never overdue, so not ranked


def test_chart_notes_say_where_the_numbers_came_from(report):
    web = render.render(dict(report, charts_source="web"))
    assert web.count("As shown on PeopleTray") == 2
    api = render.render(dict(report, charts_source="api"))
    assert "As shown on PeopleTray" not in api and "issued but not yet submitted" in api
    fallback = render.render(dict(report, charts_source="api_fallback"))
    assert fallback.count("PeopleTray sign-in failed") == 2


def test_pie_has_a_colour_for_every_slice(report):
    slices = [(f"Workflow {i:02d}", 20 - i) for i in range(14)]
    section = section_of(render.render(dict(report, open_workflows=slices)), "open-workflows")
    assert section.count("<path") == 14 and section.count("<li>") == 14
