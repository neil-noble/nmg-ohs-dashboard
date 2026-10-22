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
    # The one thing from outside is the ERT dashboard's frame, and the script that sizes it.
    assert page.count("<script") == 1 and "ert-frame" in render.ERT_FIT_SCRIPT
    assert re.findall(r'(?:src|href)="(https?://[^"]+)"', page) == [config.ERT_SITE_URL]
    assert "<img" not in page                      # no logo: the Wix page above already carries it


def test_every_section_is_present(page):
    for section in ("kpis", "event-table", "rate-trends", "event-trend", "event-mix",
                    "injury-classes", "injury-analysis", "status", "open-workflows",
                    "sheq-actions"):
        assert f'id="{section}"' in page


def test_header_shows_month_and_timestamp(page):
    assert "September 2026" in page
    assert "11 Oct 2026, 18:30 AWST" in page


def test_table_rows_and_cells(page):
    table = section_of(page, "event-table")
    assert "<th>Mining</th>" not in table          # bucket headings span Jul, Aug, Sep and FYTD
    assert re.search(r'colspan="4"[^>]*>Mining<', table)
    assert re.search(r'colspan="4"[^>]*>Exploration<', table)
    assert table.count("<th>Jul</th><th>Aug</th><th>Sep</th><th>FYTD</th>") == 2
    assert re.search(r"<th[^>]*>Total Person Hours Worked</th>(<td>[^<]*</td>){2}<td>30,500</td>"
                     r"<td>90,500</td>(<td>[^<]*</td>){2}<td>3,000</td><td>6,500</td>", table)
    assert re.search(r"<th[^>]*>Lost Time Injury Freq Rate \(LTIFR\)</th><td>NA</td><td>NA</td>"
                     r"<td>NA</td><td>0.00</td><td>NA</td><td>NA</td><td>NA</td><td>64.52</td>", table)


def test_kpi_tiles(page):
    assert page.count('class="v kpi"') == 5                # one card per measure, both buckets on it
    assert "Days since last LTI" in page and ">58<" in page
    assert ">64.52<" in page and ">30,500<" in page


def test_charts_are_inline_svg_with_month_labels(page):
    assert page.count("<svg") == 10   # rates for Mining, Exploration and combined, event bars, two
                                      # donuts, workflow pie, action bars, reporting for each area
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
    assert page.count("<svg") == 9                # no pie when nothing is open
    assert "No open workflows" in page
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


def test_events_by_month_is_a_bar_for_each_type_in_each_month(page, report):
    section = section_of(page, "event-trend")
    assert "<polyline" not in section
    nonzero = sum(1 for _, values in report["event_trend"]["series"] for v in values if v)
    assert section.count("<rect") == nonzero                 # zero months draw no bar
    assert "Sep 26 \u2013 Injury: " in section                # each bar says what it is
    for name in config.TREND_GROUPS:
        assert name in section


def test_outstanding_actions_are_listed_with_their_actionee(page):
    section = re.search(r'id="open-actions".*?</section>', page, re.S).group()
    assert "Otto OWNER" in section and "Petra ACTIONEE" in section
    assert "Fit the &lt;new&gt; guard" in section and "<new>" not in section
    assert "Overdue 9 days" in section and "Due in 21 days" in section
    assert section.index("Otto OWNER") < section.index("Petra ACTIONEE")
    assert "<th>Contractor</th>" in section and "Acme Haulage" in section
    assert "Petra &amp; Sons" in section


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


def test_no_overdue_ranking_of_actionees(page):
    assert "overdue-history" not in page and "Most overdue actions" not in page


def test_emergency_response_is_the_live_ert_dashboard(page):
    section = section_of(page, "ert-dashboard")
    assert f'<iframe id="ert-frame" src="{config.ERT_SITE_URL}"' in section
    for gone in ('id="ert-shortfalls"', 'id="ozland-ert"', "Emergency Services non-conformances"):
        assert gone not in page


def ozland_page(report):
    return render.render_ozland(report)


def test_ozland_ert_bars_are_green_or_red_with_percentages(report):
    section = section_of(ozland_page(report), "ozland-ert")
    assert section.count("<rect") == 3
    assert section.count('fill="#2E9E44"><title>') == 1 and section.count('fill="#D94F32"><title>') == 2
    assert '<b class="ok">33% Compliant</b>' in section and "1 of 3 days" in section
    assert '<b class="alert">67% Not Compliant</b>' in section and "2 of 3 days" in section
    assert "10 Oct 2026: 2 qualified on day shift, 2 on night shift - met" in section
    assert "no roster before 8 Oct 2026" in section


def test_ozland_ert_with_no_roster(report):
    page = ozland_page(dict(report, ozland_ert=dict(report["ozland_ert"], days=[], met=0, missed=0)))
    assert "no roster for this financial year" in section_of(page, "ozland-ert")


def test_visuals_sit_under_their_section(page):
    def at(ident):
        return page.index(f'id="{ident}"')

    summary = ("kpis",)
    leading = ("reporting-trend", "reporting-trend-mining", "reporting-trend-exploration", "reporting-table", "status", "sheq-actions", "open-workflows", "open-actions")
    lagging = ("rate-trends", "rate-trend-mining", "rate-trend-exploration", "rate-trend-combined",
               "event-table", "injury-classes", "event-mix", "event-trend",
               "event-status", "injury-analysis", "open-incidents")
    emergency = ("ert-dashboard",)
    assert all(at(v) < at("health-safety") for v in summary)
    assert at("health-safety") < at("leading") < at("lagging") < at("emergency-response")
    assert all(at("leading") < at(v) < at("lagging") for v in leading)
    assert all(at("lagging") < at(v) < at("emergency-response") for v in lagging)
    assert all(at("emergency-response") < at(v) for v in emergency)
    assert ">Health &amp; Safety<" in page and ">Emergency Response<" in page
    assert ">Leading indicators<" in page and ">Lagging indicators<" in page


def test_trifr_and_ltifr_for_mining_exploration_and_combined(page):
    for area in ("mining", "exploration", "combined"):
        section = section_of(page, f"rate-trend-{area}")
        assert f"TRIFR and LTIFR \u2013 {area.title()}" in section
        assert section.count("<svg") == 1 and section.count("<polyline") == 2
        assert section.count(f'stroke-dasharray="{render.RATE_DASH}"') == 1     # LTIFR is dashed
    assert "both areas&rsquo; hours" in section_of(page, "rate-trend-combined")
    assert "TRIFR 12 Month Trend<" not in page and "LTIFR 12 Month Trend<" not in page


def test_near_miss_and_hazard_reporting_visuals(page):
    for which in (config.MINING, config.EXPLORATION):
        trend = section_of(page, f"reporting-trend-{which.lower()}")
        assert f"Near miss and hazard reporting – {which}" in trend
        assert trend.count("<polyline") == 2
        assert "Near misses" in trend and "Hazard reports" in trend
    table = section_of(page, "reporting-table")
    assert re.search(r'colspan="4"[^>]*>Mining<', table) and re.search(r'colspan="4"[^>]*>Exploration<', table)
    assert table.count("<th>Jul</th><th>Aug</th><th>Sep</th><th>FYTD</th>") == 2
    assert ("<th scope=\"row\">Hazard reports</th><td>1</td><td>–</td><td>2</td><td>3</td>"
            "<td>–</td><td>1</td><td>–</td><td>1</td>") in table


def test_ozland_page_keeps_what_the_ert_dashboard_reads(report):
    # The ERT dashboard's ozland.py parses this page: the section, its period, the per-day bar
    # titles, the requirement line and the "Data as at" timestamp must all stay as they are.
    page = ozland_page(report)
    assert page.startswith("<!doctype html>") and "<script" not in page
    assert re.search(r'<section id="ozland-ert"[^>]*><h2>[^<]*<small>[^<]+</small>', page)
    assert re.search(r"<title>\d{1,2} \w{3} \d{4}: \d+ qualified on day shift, \d+ on night shift - "
                     r"(met|not met)</title>", page)
    assert "required: 2 day + 2 night" in page
    assert re.search(r"Data as at\s*(?:<[^>]+>\s*)*11 Oct 2026, 18:30 AWST", page)


def test_open_incidents_name_the_actionee(page):
    section = section_of(page, "open-incidents")
    assert "<th>Completion step</th><th>Actionee</th><th>Contractor</th>" in section
    assert "<td>Assess the Event</td><td>Otto owner</td><td>Acme Haulage</td>" in section


def test_close_out_says_so_when_the_web_app_was_not_read(page):
    section = section_of(page, "close-out")
    assert "could not be read" in section and "<svg" not in section


def test_close_out_pies_for_nmg_and_ozland():
    from tests.test_metrics_report import WEB
    raw = dict(sample.RAW, web_charts=dict(WEB, closed_events={}))
    report = metrics.build_report(raw, sample.TODAY, "x")
    report["close_out"]["companies"]["NMG"].update(on_time=3, late=1, open_overdue=1, not_due=2)
    page = render.render(report)
    nmg = section_of(page, "close-out-nmg")
    assert "Incident close-out &ndash; NMG" in nmg or "Incident close-out – NMG" in nmg
    assert "Closed by the due date" in nmg
    assert "Overdue" in nmg and "<b>1</b><em>25%</em>" in nmg and "<b>3</b><em>75%</em>" in nmg
    assert "Not in the pie: 1 still open past the due date, 2 open and not yet due" in nmg
    ozland = section_of(page, "close-out-ozland")
    assert "No incidents closed." in ozland
    assert page.index('id="open-incidents"') < page.index('id="close-out-nmg"') < page.index(
        'id="close-out-ozland"') < page.index('id="emergency-response"')
