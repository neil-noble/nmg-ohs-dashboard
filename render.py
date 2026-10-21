"""The report dict as one self-contained HTML page, laid out like a Power BI report:
a grey canvas carrying white "visuals" on a 12-column grid. No data logic here."""
import math
from html import escape
from itertools import cycle

import config

CSS = """
:root{--navy:#083045;--river:#55848A;--gold:#927128;--pale-gold:#B19045;--sand:#F1DCAA;
--sand-tint:#F8EED5;--grey:#DBDBD3;--grey-tint:#EDEDE9;--river-tint:#AAC2C5;--ink:#252423;
--muted:#605E5C;--line:#E1DFDD;--canvas:#F3F2F1}
*{box-sizing:border-box}
body{margin:0;background:var(--canvas);color:var(--ink);
font-family:"Proxima Nova",Aptos,"Segoe UI",system-ui,sans-serif;font-size:13px;line-height:1.4}
header{background:var(--navy);color:#fff;border-bottom:3px solid var(--pale-gold)}
header .bar{max-width:1440px;margin:0 auto;padding:10px 14px;display:flex;align-items:center;
gap:16px;flex-wrap:wrap}
header h1{margin:0;font-size:20px;font-weight:700;line-height:1.15}
header p{margin:1px 0 0;font-size:12px;color:var(--river-tint)}
.slicers{margin-left:auto;display:flex;gap:8px;flex-wrap:wrap}
.slicer{background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.28);border-radius:3px;
padding:4px 10px;min-width:120px}
.slicer span{display:block;font-size:10px;text-transform:uppercase;letter-spacing:.06em;
color:var(--river-tint)}
.slicer b{font-size:14px;font-weight:700}
.canvas{max-width:1440px;margin:0 auto;padding:10px 14px 18px;display:grid;
grid-template-columns:repeat(12,minmax(0,1fr));gap:10px}
.group{display:contents}
.col{grid-column:span 5;display:flex;flex-direction:column;gap:10px;min-width:0}
.col .v{flex:1 1 auto}
.v{grid-column:span var(--span,12);background:#fff;border:1px solid var(--line);border-radius:4px;
padding:10px 12px 12px;box-shadow:0 1px 2px rgba(0,0,0,.05);min-width:0}
.v>h2{margin:0 0 8px;font-size:13px;font-weight:700;color:var(--ink)}
.v>h2 small{font-weight:400;color:var(--muted);font-size:12px}
.note{color:var(--muted);font-size:11.5px;margin:8px 0 0}
#notice{grid-column:1/-1;background:var(--sand-tint);border-left:4px solid var(--pale-gold);
padding:9px 12px;border-radius:3px}
.kpis{grid-column:1/-1;display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px}
.v.kpi{grid-column:auto;border-top:3px solid var(--river)}
.pair{display:flex;gap:10px}
.pair>div{flex:1;min-width:0}
.pair b{display:block;font-size:30px;font-weight:700;line-height:1.1;font-variant-numeric:tabular-nums}
.pair b.long{font-size:15px;line-height:1.25;padding:5px 0 4px}
.pair span{font-size:11px;color:var(--muted);display:flex;align-items:center;gap:5px;margin-top:2px}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;flex:none}
.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;min-width:480px;font-size:12.5px}
th,td{padding:4px 8px;border-bottom:1px solid var(--line);text-align:right}
thead th{font-weight:700;color:var(--ink);border-bottom:2px solid var(--navy);white-space:nowrap}
.matrix thead tr:first-child th{border-bottom:1px solid var(--line);text-align:center;color:#fff}
.matrix thead tr:first-child th:first-child{background:none}
thead th:first-child,tbody th{text-align:left}
tbody th{font-weight:400}
tbody tr:nth-child(even){background:#FAF9F8}
tbody tr.bold th,tbody tr.bold td{font-weight:700;background:var(--grey-tint);
border-top:1px solid var(--navy)}
tbody td{font-variant-numeric:tabular-nums}
svg{width:100%;height:auto;display:block}
svg .grid{stroke:var(--line);stroke-width:1}
svg .tick{font-size:10px;fill:var(--muted)}
svg .dlabel{font-size:10.5px;font-weight:700}
svg .donut-total{font-size:8px;font-weight:700;fill:var(--ink)}
svg .donut-cap{font-size:2.6px;fill:var(--muted)}
.legend{display:flex;gap:4px 14px;justify-content:center;flex-wrap:wrap;font-size:11.5px;margin-top:6px;
color:var(--muted)}
.legend span{display:flex;align-items:center;gap:5px}
.dash{display:inline-block;width:18px;border-top:2.5px dashed;flex:none}
.donut{display:flex;align-items:center;gap:12px}
.donut svg{flex:0 0 46%;max-width:190px}
.donut ul{list-style:none;margin:0;padding:0;flex:1;min-width:0;font-size:12px}
.donut li{display:flex;align-items:center;gap:6px;padding:2px 0;border-bottom:1px solid var(--grey-tint)}
.donut li span.name{flex:1;min-width:0}
.donut li b{font-variant-numeric:tabular-nums}
.donut li em{font-style:normal;color:var(--muted);width:36px;text-align:right}
.hbars{display:grid;grid-template-columns:minmax(90px,44%) 1fr;gap:5px 8px;align-items:center;font-size:12px}
.brow{display:flex;align-items:center;gap:5px;height:14px}
.brow i{display:block;height:12px;border-radius:2px;min-width:2px}
.brow em{font-style:normal;font-weight:700;font-variant-numeric:tabular-nums;font-size:11.5px}
.stack{display:flex;flex-direction:column;gap:2px}
.cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;text-align:center}
.cards div{background:var(--canvas);border-radius:3px;padding:10px 4px}
.cards b{display:block;font-size:28px;font-weight:700;color:var(--navy);line-height:1.1}
.cards b.alert{color:#A4262C}
.cards b.ok{color:#2E9E44}
.cards.two{grid-template-columns:repeat(2,minmax(0,1fr));margin-top:8px}
.cards span{font-size:11px;color:var(--muted)}
.actions th,.actions td{text-align:left;vertical-align:top}
.actions td:nth-child(n+2){white-space:nowrap}
.pill{display:inline-block;border-radius:10px;padding:1px 9px;font-size:11.5px;font-weight:700;
background:var(--grey-tint);color:var(--ink)}
.pill.late{background:#FDE7E9;color:#A4262C}
.bars3{max-width:420px;margin:0 auto}
svg .cat{font-size:12px;fill:var(--ink)}
svg .val{font-size:14px;font-weight:700}
details{margin-top:8px;font-size:12px}
details summary{cursor:pointer;color:var(--river)}
.band{grid-column:1/-1;background:var(--navy);color:#fff;border-radius:4px;padding:9px 14px;
margin-top:8px;border-left:6px solid var(--pale-gold)}
.band h2{margin:0;font-size:17px;font-weight:700;letter-spacing:.01em}
.band p{margin:2px 0 0;font-size:12px;color:var(--river-tint)}
.sub{grid-column:1/-1;display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;
border-bottom:2px solid var(--river);padding:4px 2px 3px}
.sub h3{margin:0;font-size:14px;font-weight:700;color:var(--navy);text-transform:uppercase;
letter-spacing:.05em}
.sub p{margin:0;font-size:12px;color:var(--muted)}
footer{grid-column:1/-1;color:var(--muted);font-size:11px;padding:2px 2px 0}
footer p{margin:3px 0}
@media(max-width:1000px){.v,.col{grid-column:1/-1}.kpis{grid-template-columns:repeat(2,minmax(0,1fr))}
.v.kpi{grid-column:auto}.slicers{margin-left:0}}
@media(max-width:480px){.kpis{grid-template-columns:1fr}.donut{flex-direction:column;align-items:stretch}
.donut svg{max-width:170px;margin:0 auto}}
"""

W, H, LEFT, RIGHT, TOP, BOTTOM = 560, 250, 36, 44, 16, 28
DONUT_R = 15.915          # circumference 100, so dash lengths are percentages
RED = "#A4262C"
OPEN_CLOSED_COLOURS = (RED, config.RIVER)
SHEQ_COLOURS = ("#B5B5B0", "#2E9E44", "#D94F32")        # assigned, due, overdue - as PeopleTray
MET_COLOUR, MISSED_COLOUR = "#2E9E44", "#D94F32"
REPORTING_COLOURS = dict(zip(config.REPORTING_SERIES, (config.RIVER, MET_COLOUR)))
RATE_DASH = "6 4"                   # LTIFR is drawn dashed on the combined rate chart
PIE_COLOURS = (config.RIVER, config.GOLD, config.NAVY, "#D8C8A2", "#8498A2", config.PALE_GOLD,
               "#AAC2C5", "#99999A", config.SAND, config.BLACK, "#C9B894", "#3D6B70", "#5B4718",
               "#2F5F7A")
WEB_NOTE = "As shown on PeopleTray&rsquo;s SHEQ home page."
WEB_PIE_NOTE = WEB_NOTE + " Exploration Daily Prestarts are left out."
FALLBACK_NOTE = ("PeopleTray sign-in failed at this build, so these are the API figures and may "
                 "differ from PeopleTray&rsquo;s own chart.")


def nice_max(value):
    """Smallest of 5, 10, 25, 50, 100, 250, ... that is not below value."""
    step = 1
    while True:
        for multiple in (5, 10, 25):
            if value <= step * multiple:
                return step * multiple
        step *= 10


def _visual(span, title, body, ident=None, classes="", sub=""):
    attr = f' id="{ident}"' if ident else ""
    small = f" <small>{escape(sub)}</small>" if sub else ""
    return (f'<section{attr} class="v{" " + classes if classes else ""}" style="--span:{span}">'
            f"<h2>{escape(title)}{small}</h2>{body}</section>")


def _legend(items, dashed=()):
    def swatch(name, colour):
        if name in dashed:
            return f'<i class="dash" style="border-color:{colour}"></i>'
        return f'<i class="dot" style="background:{colour}"></i>'

    return '<div class="legend">' + "".join(
        f'<span>{swatch(name, colour)}{escape(name)}</span>' for name, colour in items) + "</div>"


def _axes(top, width, right):
    def y(v):
        return TOP + (H - TOP - BOTTOM) * (1 - v / top)

    parts = []
    for k in range(6):
        v = top * k / 5
        parts.append(f'<line class="grid" x1="{LEFT}" x2="{width - right}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>'
                     f'<text class="tick" x="{LEFT - 6}" y="{y(v) + 3.5:.1f}" text-anchor="end">{v:g}</text>')
    return parts, y


def _line_chart(title, labels, series, colours=config.SERIES_COLOURS, width=W, fmt="{:.2f}", dashed=()):
    """series and colours are both keyed by series name; fmt formats the latest-point labels;
    series named in dashed are drawn with a dashed line."""
    values = [v for line in series.values() for v in line if v is not None]
    parts, y = _axes(nice_max(max(values, default=0)), width, RIGHT)
    span = max(len(labels) - 1, 1)

    def x(i):
        return LEFT + (width - LEFT - RIGHT) * i / span

    for i, label in enumerate(labels):
        parts.append(f'<text class="tick" x="{x(i):.1f}" y="{H - 9}" text-anchor="middle">{escape(label)}</text>')
    label_ys = []
    for name, line in series.items():
        colour = colours[name]
        dash = f' stroke-dasharray="{RATE_DASH}"' if name in dashed else ""
        run = []
        for i, v in enumerate(list(line) + [None]):       # the trailing None flushes the last run
            if v is None:
                if len(run) > 1:
                    parts.append(f'<polyline fill="none" stroke="{colour}" stroke-width="2.5" '
                                 f'stroke-linejoin="round"{dash} points="{" ".join(run)}"/>')
                run = []
            else:
                run.append(f"{x(i):.1f},{y(v):.1f}")
                parts.append(f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="3" fill="{colour}"/>')
        if line and line[-1] is not None:
            # Data label on the latest point, nudged clear of the other series' label.
            at = y(line[-1]) + 4
            while any(abs(at - other) < 12 for other in label_ys):
                at -= 12
            label_ys.append(at)
            parts.append(f'<text class="dlabel" x="{x(len(line) - 1) + 7:.1f}" y="{at:.1f}" '
                         f'fill="{colour}">{fmt.format(line[-1])}</text>')
    svg = f'<svg viewBox="0 0 {width} {H}" role="img" aria-label="{escape(title)}">{"".join(parts)}</svg>'
    return svg + _legend([(name, colours[name]) for name in series], dashed)


def _donut(title, items, colours, caption):
    """items: [(name, count)]. A ring with the total in the middle and a legend with shares."""
    total = sum(n for _, n in items)
    ring = (f'<circle cx="21" cy="21" r="{DONUT_R}" fill="none" stroke="{config.COOL_GREY}" '
            'stroke-width="6"/>')
    drawn = 0.0
    for (name, n), colour in zip(items, colours):
        share = n / total * 100 if total else 0.0
        if n:
            ring += (f'<circle cx="21" cy="21" r="{DONUT_R}" fill="none" stroke="{colour}" '
                     f'stroke-width="6" stroke-dasharray="{share:.3f} {100 - share:.3f}" '
                     f'stroke-dashoffset="{125 - drawn:.3f}"><title>{escape(name)}: {n}</title></circle>')
            drawn += share
    svg = (f'<svg viewBox="0 0 42 42" role="img" aria-label="{escape(title)}">{ring}'
           f'<text class="donut-total" x="21" y="22.5" text-anchor="middle">{total}</text>'
           f'<text class="donut-cap" x="21" y="27" text-anchor="middle">{escape(caption)}</text></svg>')
    return f'<div class="donut">{svg}<ul>{_share_rows(items, colours, total)}</ul></div>'


def _share_rows(items, colours, total):
    return "".join(
        f'<li><i class="dot" style="background:{colour}"></i><span class="name">{escape(name)}</span>'
        f"<b>{n}</b><em>{(n / total * 100 if total else 0):.0f}%</em></li>"
        for (name, n), colour in zip(items, colours))


def _pie(title, items, colours):
    """A filled pie with a legend carrying counts and shares. Assumes at least one item."""
    total = sum(n for _, n in items)
    wedges, start = "", 0.0
    colours = [colour for _, colour in zip(items, cycle(colours))]     # never run out of colours
    for (name, n), colour in zip(items, colours):
        share = n / total
        tip = f"<title>{escape(name)}: {n}</title>"
        if share > 0.9999:
            wedges += f'<circle cx="21" cy="21" r="19" fill="{colour}">{tip}</circle>'
        elif n:
            a0, a1 = (2 * math.pi * turn - math.pi / 2 for turn in (start, start + share))
            wedges += (f'<path d="M21 21 L{21 + 19 * math.cos(a0):.3f} {21 + 19 * math.sin(a0):.3f} '
                       f'A19 19 0 {int(share > 0.5)} 1 {21 + 19 * math.cos(a1):.3f} '
                       f'{21 + 19 * math.sin(a1):.3f} Z" fill="{colour}" stroke="#fff" '
                       f'stroke-width="0.4">{tip}</path>')
        start += share
    svg = f'<svg viewBox="0 0 42 42" role="img" aria-label="{escape(title)}">{wedges}</svg>'
    return f'<div class="donut">{svg}<ul>{_share_rows(items, colours, total)}</ul></div>'


def _bar_chart(title, items, colours):
    """Vertical bars with the value above each and its name below."""
    width, right = 360, 12
    # 15% headroom so the value above the tallest bar is never clipped by the top edge.
    parts, y = _axes(nice_max(max((n for _, n in items), default=0) * 1.15), width, right)
    slot = (width - LEFT - right) / max(len(items), 1)
    bar = slot * 0.5
    for i, ((name, n), colour) in enumerate(zip(items, colours)):
        centre = LEFT + slot * (i + 0.5)
        parts.append(f'<rect x="{centre - bar / 2:.1f}" y="{y(n):.1f}" width="{bar:.1f}" '
                     f'height="{y(0) - y(n):.1f}" fill="{colour}"><title>{escape(name)}: {n}</title></rect>'
                     f'<text class="val" x="{centre:.1f}" y="{y(n) - 5:.1f}" text-anchor="middle" '
                     f'fill="{colour}">{n}</text>'
                     f'<text class="cat" x="{centre:.1f}" y="{H - 8}" text-anchor="middle">{escape(name)}</text>')
    return (f'<div class="bars3"><svg viewBox="0 0 {width} {H}" role="img" '
            f'aria-label="{escape(title)}">{"".join(parts)}</svg></div>')


def _bar(value, longest, colour):
    share = value / longest if longest else 0
    return (f'<div class="brow"><i style="width:calc((100% - 30px) * {share:.3f});background:{colour}">'
            f"</i><em>{value}</em></div>")


def _header(report):
    return ('<header><div class="bar">'
            "<div><h1>Health &amp; Safety Performance</h1><p>New Murchison Gold Limited</p></div>"
            '<div class="slicers">'
            f'<div class="slicer"><span>Reporting month</span><b>{escape(report["month_label"])}</b></div>'
            '<div class="slicer"><span>Financial year</span><b>From 1 July</b></div>'
            f'<div class="slicer"><span>Data as at</span><b>{escape(report["generated"])}</b></div>'
            "</div></div></header>")


def _notice(report):
    lines = []
    if report["unmapped"]:
        names = ", ".join(escape(name) for name in report["unmapped"])
        lines.append(f"<strong>Unmapped workgroup:</strong> {names}. Events and hours for "
                     "these are not included in the figures below until they are assigned to "
                     "Mining or Exploration.")
    if report["undated"]:
        plural = "event has" if report["undated"] == 1 else "events have"
        lines.append(f'<strong>Undated:</strong> {report["undated"]} {plural} no date in '
                     "PeopleTray and could not be counted.")
    return f'<div id="notice">{"<br>".join(lines)}</div>' if lines else ""


def _kpis(report):
    cards = []
    measures = [label for label, _ in report["kpis"][config.BUCKETS[0]]]
    for index, label in enumerate(measures):
        halves = ""
        for name in config.BUCKETS:
            value = report["kpis"][name][index][1]
            size = ' class="long"' if len(value) > 7 else ""
            colour = config.SERIES_COLOURS[name]
            halves += (f'<div><b{size} style="color:{colour}">{escape(value)}</b>'
                       f'<span><i class="dot" style="background:{colour}"></i>{escape(name)}</span></div>')
        cards.append(f'<section class="v kpi"><h2>{escape(label)}</h2><div class="pair">{halves}</div></section>')
    return f'<div id="kpis" class="kpis">{"".join(cards)}</div>'


def _matrix(report, rows, first_heading):
    """Rows of Mining month, Mining FYTD, Exploration month, Exploration FYTD cells."""
    month = escape(report["month_label"].split(" ")[0])
    heads = "".join(f'<th colspan="2" style="background:{config.SERIES_COLOURS[name]}">{escape(name)}</th>'
                    for name in config.BUCKETS)
    subs = "".join(f"<th>{month}</th><th>FYTD</th>" for _ in config.BUCKETS)
    body = "".join(
        ('<tr class="bold">' if row["bold"] else "<tr>")
        + f'<th scope="row">{escape(row["label"])}</th>'
        + "".join(f"<td>{escape(cell)}</td>" for cell in row["cells"]) + "</tr>"
        for row in rows)
    return (f'<div class="scroll"><table class="matrix"><thead><tr><th></th>{heads}</tr>'
            f"<tr><th>{escape(first_heading)}</th>{subs}</tr></thead><tbody>{body}</tbody></table></div>")


def _table(report):
    inner = (_matrix(report, report["table"], "Event")
             + '<p class="note">Frequency rates in the FYTD columns are rolling 12-month rates. '
             "Head count is NMG employees only, at month end.</p>")
    return _visual(7, "Events", inner, "event-table", sub="month and financial year to date")


def _trends(report):
    """TRIFR and LTIFR on one chart (Neil, 2026-10-21): colour is the area, LTIFR is dashed."""
    trend = report["trend"]
    series, colours, dashed = {}, {}, []
    for measure in ("TRIFR", "LTIFR"):
        for name in config.BUCKETS:
            key = f"{measure} {name}"
            series[key] = trend[measure.lower()][name]
            colours[key] = config.SERIES_COLOURS[name]
            if measure == "LTIFR":
                dashed.append(key)
    note = ('<p class="note">Injuries per one million hours worked, calculated over a rolling '
            "12 months. TRIFR counts lost time, restricted work and medically treated injuries; "
            "LTIFR counts lost time injuries only, so it is never above TRIFR. Where an area&rsquo;s "
            "two lines are equal they overlap.</p>")
    chart = _line_chart("TRIFR and LTIFR 12 Month Trend", trend["labels"], series, colours,
                        width=1100, dashed=dashed)
    return _visual(12, "TRIFR and LTIFR 12 Month Trend", chart + note, "rate-trends",
                   sub="total recordable and lost time injury frequency rates")


def _event_trend(report):
    trend = report["event_trend"]
    head = "".join(f"<th>{escape(label)}</th>" for label in trend["labels"])
    rows = "".join(f'<tr><th scope="row">{escape(name)}</th>'
                   + "".join(f"<td>{value or '–'}</td>" for value in values) + "</tr>"
                   for name, values in trend["series"])
    colours = dict(zip((name for name, _ in trend["series"]), config.TREND_COLOURS))
    inner = (_line_chart("Events by month", trend["labels"], dict(trend["series"]), colours,
                         width=760, fmt="{}")
             + "<details><summary>Show the numbers</summary><div class=\"scroll\"><table><thead>"
             f"<tr><th>Type</th>{head}</tr></thead><tbody>{rows}</tbody></table></div></details>")
    return _visual(8, "Events by month", inner, "event-trend",
                   sub="last 12 months, Mining and Exploration combined")


def _reporting(report, beside=""):
    """Leading: near misses and hazards reported, by month and as a month / FYTD table, with
    beside stacked under the table."""
    reporting = report["reporting"]
    chart = _line_chart("Near miss and hazard reporting", reporting["labels"], dict(reporting["series"]),
                        REPORTING_COLOURS, width=640, fmt="{}")
    note = ('<p class="note">Near misses are safety events of type Near Miss; hazard reports are '
            "Hazard Report Forms submitted in PeopleTray. More reporting is a good sign.</p>")
    return ('<div id="reporting" class="group">'
            + _visual(7, "Near miss and hazard reporting", chart, "reporting-trend",
                      sub="last 12 months, Mining and Exploration combined")
            + '<div class="col">'
            + _visual(5, "Reports by area", _matrix(report, reporting["table"], "Report") + note,
                      "reporting-table", sub="month and financial year to date")
            + beside + "</div></div>")


def _event_mix(report):
    items = [(name, sum(values)) for name, values in report["event_trend"]["series"]]
    return _visual(4, "Events by type", _donut("Events by type", items, config.TREND_COLOURS, "events"),
                   "event-mix", sub="last 12 months")


def _injury_classes(report):
    longest = max((n for _, values in report["injury_classes"] for n in values.values()), default=0)
    rows = ""
    for label, values in report["injury_classes"]:
        bars = "".join(_bar(values[name], longest, config.SERIES_COLOURS[name]) for name in config.BUCKETS)
        rows += f'<span>{escape(label)}</span><div class="stack">{bars}</div>'
    legend = _legend([(name, config.SERIES_COLOURS[name]) for name in config.BUCKETS])
    return _visual(5, "Injuries by classification", f'<div class="hbars">{rows}</div>{legend}',
                   "injury-classes", sub="financial year to date")


def _injuries(report):
    visuals = ""
    for title, items in report["injury_analysis"]:
        longest = max((n for _, n in items), default=0)
        rows = "".join(f"<span>{escape(label)}</span>{_bar(n, longest, config.RIVER)}" for label, n in items)
        inner = f'<div class="hbars">{rows}</div>' if items else \
            '<p class="note">No injuries recorded in the last 12 months.</p>'
        visuals += _visual(4, title, inner, sub="injuries, last 12 months")
    return f'<div id="injury-analysis" class="group">{visuals}</div>'


def _event_status(report):
    status = report["status"]
    donut = _donut("Event status", [("Open", status["events_open"]), ("Closed", status["events_closed"])],
                   OPEN_CLOSED_COLOURS, "events")
    return _visual(4, "Event status", donut, "event-status", sub="last 12 months")


def _actions(report):
    status = report["status"]
    overdue = ' class="alert"' if status["actions_overdue"] else ""
    cards = (f'<div class="cards"><div><b>{status["actions_open"]}</b><span>Open</span></div>'
             f'<div><b{overdue}>{status["actions_overdue"]}</b><span>Overdue</span></div>'
             f'<div><b>{status["actions_closed_month"]}</b><span>Closed in month</span></div></div>'
             '<p class="note">All corrective actions on site, not split by Mining and Exploration.</p>')
    return _visual(5, "Corrective actions", cards, "status")


def _pill(text, late):
    return f'<span class="pill{" late" if late else ""}">{escape(text)}</span>'


def _open_actions(report):
    rows = "".join(
        f'<tr><td>{escape(a["action"])}</td><td>{escape(a["actionee"])}</td>'
        f'<td>{escape(a["contractor"])}</td><td>{escape(a["due"])}</td>'
        f'<td>{_pill(a["status"], a["overdue"])}</td></tr>'
        for a in report["open_actions"])
    inner = ('<div class="scroll"><table class="actions"><thead><tr><th>Action</th><th>Actionee</th>'
             f"<th>Contractor</th><th>Due</th><th>Status</th></tr></thead><tbody>{rows}</tbody></table></div>"
             if rows else '<p class="note">No outstanding actions.</p>')
    return _visual(12, "Outstanding corrective actions", inner, "open-actions",
                   sub=f'{len(report["open_actions"])} open, most overdue first')


def _open_incidents(report):
    incidents = report["open_incidents"]
    rows = "".join(
        f'<tr><td>{escape(e["event"])}</td><td>{escape(e["date"])}</td><td>{escape(e["type"])}</td>'
        f'<td>{escape(e["workgroup"])}</td><td>{escape(e["step"])}</td>'
        f'<td>{escape(e["contractor"])}</td><td>{escape(e["due"])}</td>'
        f'<td>{_pill(e["status"], e["overdue"])}</td></tr>'
        for e in incidents["rows"])
    inner = ('<div class="scroll"><table class="actions incidents"><thead><tr><th>Event</th><th>Date</th>'
             "<th>Type</th><th>Workgroup</th><th>Completion step</th><th>Contractor</th>"
             f"<th>Target close</th><th>Status</th></tr></thead><tbody>{rows}</tbody></table></div>"
             '<p class="note">Open safety events in PeopleTray against their target close date. The '
             "contractor is the employer of the person the event was reported to.</p>"
             if rows else '<p class="note">No open incidents.</p>')
    shown = len(incidents["rows"])
    sub = (f'{incidents["total"]} open, most overdue first' if shown == incidents["total"]
           else f'top {shown} of {incidents["total"]} open, most overdue first')
    return _visual(12, "Open incidents", inner, "open-incidents", sub=sub)


def _ozland_chart(days):
    """One bar per rostered day: qualified Ozland ERT members on site, green when both shifts
    had their two, red when not. A day with nobody qualified still gets a red stub."""
    width, right = 1100, 12
    required = 2 * config.OZLAND_ERT_PER_SHIFT
    top = max(max((d["day_shift"] + d["night_shift"] for d in days), default=0), required) + 1
    parts, y = _axes(top, width, right)
    slot = (width - LEFT - right) / len(days)
    bar = max(slot * 0.7, 1)
    for i, d in enumerate(days):
        n = d["day_shift"] + d["night_shift"]
        x = LEFT + slot * i + (slot - bar) / 2
        tall = max(y(0) - y(n), 3)
        colour = MET_COLOUR if d["met"] else MISSED_COLOUR
        tip = (f'{d["label"]}: {d["day_shift"]} qualified on day shift, {d["night_shift"]} on night '
               f'shift - {"met" if d["met"] else "not met"}')
        parts.append(f'<rect x="{x:.1f}" y="{y(0) - tall:.1f}" width="{bar:.1f}" height="{tall:.1f}" '
                     f'fill="{colour}"><title>{escape(tip)}</title></rect>')
        if i == 0 or d["day"].day == 1:
            parts.append(f'<text class="tick" x="{x:.1f}" y="{H - 9}">{escape(d["label"][:-5])}</text>')
    parts.append(f'<line x1="{LEFT}" x2="{width - right}" y1="{y(required):.1f}" y2="{y(required):.1f}" '
                 f'stroke="{config.NAVY}" stroke-width="1.5" stroke-dasharray="5 4"/>'
                 f'<text class="tick" x="{width - right}" y="{y(required) - 5:.1f}" text-anchor="end">'
                 f"required: {config.OZLAND_ERT_PER_SHIFT} day + {config.OZLAND_ERT_PER_SHIFT} night</text>")
    # Too many days to read squeezed onto a phone, so it scrolls sideways there instead.
    return (f'<div class="scroll"><svg viewBox="0 0 {width} {H}" style="min-width:720px" role="img" '
            f'aria-label="Ozland ERT obligation by day">{"".join(parts)}</svg></div>')


def _ozland_ert(report):
    oz = report["ozland_ert"]
    days = oz["days"]
    if not days:
        inner = '<p class="note">PeopleTray holds no roster for this financial year yet.</p>'
        return _visual(12, "Ozland ERT obligation", inner, "ozland-ert")
    total = len(days)
    met_pct, missed_pct = oz["met"] / total * 100, oz["missed"] / total * 100
    start = days[0]["label"]
    late_start = days[0]["day"] > oz["fy_start"]
    inner = (_ozland_chart(days)
             + _legend([("Obligation met", MET_COLOUR), ("Not met", MISSED_COLOUR)])
             + f'<div class="cards two"><div><b class="ok">{met_pct:.0f}%</b>'
             f'<span>Compliant &ndash; {oz["met"]} of {total} days</span></div>'
             f'<div><b class="alert">{missed_pct:.0f}%</b>'
             f'<span>Not compliant &ndash; {oz["missed"]} of {total} days</span></div></div>'
             f'<p class="note">Ozland must provide {config.OZLAND_ERT_PER_SHIFT} qualified ERT members on '
             f"day shift and {config.OZLAND_ERT_PER_SHIFT} on night shift. Qualified means Competent in all "
             "six ERT competencies (Advanced First Aid, Road Crash Rescue, Fire Team Operations, Open "
             "Circuit BA, HAZMAT, Vertical Rescue). Each bar is the number of qualified Ozland ERT "
             "members rostered on that day, from the PeopleTray roster; hover a bar for the day and "
             "night split."
             + (f" PeopleTray holds no roster before {escape(start)}, so the record starts there "
                "rather than at 1 July." if late_start else "")
             + "</p>")
    return _visual(12, "Ozland ERT obligation", inner, "ozland-ert",
                   sub=f"{start} to {days[-1]['label']}, financial year to date")


def _ert_shortfalls(report):
    ert = report["ert"]
    if ert is None:
        inner = ('<p class="note">The NMG CPO ERT dashboard could not be read on this build, so '
                 "ERT coverage is not shown.</p>")
        return _visual(12, "Emergency Services non-conformances", inner, "ert-shortfalls")
    rows = "".join(
        f'<tr><td>{escape(r["shift"])}</td><td>{escape(r["competency"])}</td>'
        f'<td>{r["held"]}</td><td>{r["minimum"]}</td><td>{_pill(r["status"], True)}</td></tr>'
        for r in ert["rows"])
    inner = ('<div class="scroll"><table class="actions"><thead><tr><th>Shift</th><th>Competency</th>'
             "<th>ERT on roster</th><th>Minimum</th><th>Status</th></tr></thead>"
             f"<tbody>{rows}</tbody></table></div>"
             if rows else '<p class="note">Every ERT competency is at or above its minimum.</p>')
    when = f' as at {escape(ert["updated"])}' if ert["updated"] else ""
    inner += ('<p class="note">ERT competency coverage below minimum, from the NMG CPO ERT '
              f"dashboard{when}: competent ERT members on today&rsquo;s roster against the minimum "
              "per 24 hours.</p>")
    return _visual(12, "Emergency Services non-conformances", inner, "ert-shortfalls",
                   sub=f'{len(ert["rows"])} of {ert["dials"]} below minimum')


def _open_workflows(report):
    items = report["open_workflows"]
    total = sum(n for _, n in items)
    note = {"web": WEB_PIE_NOTE, "api_fallback": FALLBACK_NOTE}.get(
        report["charts_source"],
        "Submitted forms and safety events whose workflow is still open. PeopleTray&rsquo;s own "
        "chart also counts forms issued but not yet submitted. Exploration Daily Prestarts are "
        "left out.")
    inner = (_pie("Open workflows", items, PIE_COLOURS) + f'<p class="note">{note}</p>'
             if items else '<p class="note">No open workflows.</p>')
    return _visual(6, "Open workflows", inner, "open-workflows", sub=f"{total} open, by workflow type")


def _sheq_actions(report):
    note = {"web": WEB_NOTE, "api_fallback": FALLBACK_NOTE}.get(
        report["charts_source"],
        "Open actions for Crown Prince workgroups, as PeopleTray charts them. Overdue is past the "
        "due date, Due is inside the reminder window, Assigned is the rest.")
    inner = _bar_chart("SHEQ actions", report["sheq_actions"], SHEQ_COLOURS) + f'<p class="note">{note}</p>'
    return _visual(6, "SHEQ actions", inner, "sheq-actions", sub="assigned, due and overdue")


def _footer():
    return ("<footer><p><strong>Source:</strong> PeopleTray. Rebuilt daily.</p>"
            "<p><strong>Mining:</strong> all CPO workgroups, Contractors &ndash; Local and "
            "Contractors &ndash; Other. <strong>Exploration:</strong> all GG workgroups and "
            "Drilling Contractors. Perth office and Flight/Accommodation Only are excluded.</p>"
            "<p><strong>Recordable injuries</strong> are lost time, restricted work and medically "
            "treated injuries. Non work related and pre-existing conditions are not counted.</p></footer>")


def _band(ident, title, blurb):
    return f'<div id="{ident}" class="band"><h2>{escape(title)}</h2><p>{escape(blurb)}</p></div>'


def _sub(ident, title, blurb):
    return f'<div id="{ident}" class="sub"><h3>{escape(title)}</h3><p>{escape(blurb)}</p></div>'


def render(report):
    # Summary up top, then two sections (Neil, 2026-10-21): Health & Safety, split into leading
    # and lagging indicators, and Emergency Response.
    side = f'<div class="col">{_injury_classes(report)}{_event_mix(report)}</div>'
    main = "".join((
        _notice(report), _kpis(report),
        _band("health-safety", "Health & Safety", "Safety performance for Mining and Exploration"),
        _sub("leading", "Leading indicators",
             "activity that prevents harm: hazards and near misses reported, forms completed, "
             "corrective actions closed out"),
        _reporting(report, _actions(report)), _sheq_actions(report), _open_workflows(report), _open_actions(report),
        _sub("lagging", "Lagging indicators", "outcomes: events, injuries and frequency rates"),
        _trends(report), _table(report), side, _event_trend(report), _event_status(report),
        _injuries(report), _open_incidents(report),
        _band("emergency-response", "Emergency Response", "ERT coverage and contractor obligations"),
        _ert_shortfalls(report), _ozland_ert(report),
        _footer()))
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>NMG Health &amp; Safety Performance</title><style>{CSS}</style></head><body>"
            f'{_header(report)}<main class="canvas">{main}</main></body></html>')
