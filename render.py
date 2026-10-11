"""The report dict as one self-contained HTML page. No data logic here."""
from html import escape

import config

CSS = """
:root{--navy:#083045;--river:#55848A;--gold:#927128;--pale-gold:#B19045;--sand:#F1DCAA;
--sand-tint:#F8EED5;--grey:#DBDBD3;--grey-tint:#EDEDE9;--river-tint:#AAC2C5;--ink:#333334;--muted:#6b6b6c}
*{box-sizing:border-box}
body{margin:0;background:var(--grey-tint);color:var(--ink);
font-family:"Proxima Nova",Aptos,"Segoe UI",system-ui,sans-serif;font-size:15px;line-height:1.45}
.wrap{max-width:1180px;margin:0 auto;padding:0 16px 32px}
header{background:#fff;border-bottom:4px solid var(--gold)}
header .wrap{display:flex;align-items:center;gap:20px;flex-wrap:wrap;padding-top:14px;padding-bottom:14px}
header img{height:54px;width:auto}
.wordmark{font-weight:900;font-size:34px;color:var(--navy);letter-spacing:1px}
header h1{margin:0;font-size:24px;font-weight:900;color:var(--navy);line-height:1.15}
header p{margin:2px 0 0;color:var(--muted);font-size:13px}
header .month{margin-left:auto;text-align:right}
header .month strong{display:block;font-size:20px;color:var(--navy)}
section{background:#fff;border-radius:6px;margin-top:18px;overflow:hidden;
box-shadow:0 1px 2px rgba(8,48,69,.12)}
section>h2{margin:0;padding:9px 16px;background:var(--navy);color:#fff;font-size:14px;
font-weight:700;letter-spacing:.06em;text-transform:uppercase}
.pad{padding:16px}
.note{color:var(--muted);font-size:13px;margin:10px 0 0}
#notice{background:var(--sand-tint);border-left:5px solid var(--pale-gold);padding:12px 16px;
margin-top:18px;border-radius:4px}
.bucket{display:flex;align-items:stretch;gap:10px;flex-wrap:wrap;margin-bottom:10px}
.bucket:last-child{margin-bottom:0}
.bucket h3{flex:0 0 118px;margin:0;display:flex;align-items:center;justify-content:center;
color:#fff;border-radius:4px;font-size:15px;text-transform:uppercase;letter-spacing:.05em}
.tile{flex:1 1 150px;background:var(--grey-tint);border-radius:4px;padding:10px 12px;
border-top:3px solid var(--river)}
.tile b{display:block;font-size:26px;font-weight:900;color:var(--navy);line-height:1.2}
.tile span{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;min-width:560px}
th,td{padding:7px 10px;border-bottom:1px solid var(--grey);text-align:center}
thead th{color:#fff;font-weight:700}
thead tr:first-child th{background:var(--river-tint);color:var(--navy);font-size:16px;
letter-spacing:.05em;text-transform:uppercase}
thead tr:last-child th{background:#8498A2}
tbody th{text-align:left;font-weight:400}
tbody tr.bold th,tbody tr.bold td{font-weight:900;color:var(--navy);border-top:2px solid var(--river);
border-bottom:2px solid var(--river)}
tbody td{font-variant-numeric:tabular-nums}
tbody tr:nth-child(even){background:#fafaf8}
.cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:18px}
.card h3{margin:0 0 6px;font-size:16px;color:var(--navy);text-align:center}
svg{width:100%;height:auto;display:block}
svg .grid{stroke:var(--grey);stroke-width:1}
svg .tick{font-size:10px;fill:var(--muted)}
.legend{display:flex;gap:16px;justify-content:center;flex-wrap:wrap;font-size:13px;margin-top:6px}
.legend i{display:inline-block;width:14px;height:10px;margin-right:5px;border-radius:2px}
.bars{display:grid;grid-template-columns:minmax(110px,42%) 1fr 30px;gap:5px 8px;align-items:center;
font-size:13px}
.bars .track{background:var(--grey-tint);border-radius:3px;height:14px}
.bars .fill{background:var(--river);border-radius:3px;height:14px}
.bars .n{text-align:right;font-variant-numeric:tabular-nums;font-weight:700}
details{margin-top:10px;font-size:13px}
details summary{cursor:pointer;color:var(--river)}
footer{color:var(--muted);font-size:12px;margin-top:18px}
footer p{margin:4px 0}
@media(max-width:600px){header .month{margin-left:0;text-align:left}.bucket h3{flex:1 1 100%;padding:6px}
header h1{font-size:20px}}
"""

W, H, LEFT, RIGHT, TOP, BOTTOM = 560, 250, 40, 14, 14, 30


def nice_max(value):
    """Smallest of 5, 10, 25, 50, 100, 250, ... that is not below value."""
    step = 1
    while True:
        for multiple in (5, 10, 25):
            if value <= step * multiple:
                return step * multiple
        step *= 10


def _axes(labels, top):
    def y(v):
        return TOP + (H - TOP - BOTTOM) * (1 - v / top)

    parts = []
    for k in range(6):
        v = top * k / 5
        parts.append(f'<line class="grid" x1="{LEFT}" x2="{W - RIGHT}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>'
                     f'<text class="tick" x="{LEFT - 6}" y="{y(v) + 3.5:.1f}" text-anchor="end">{v:g}</text>')
    return parts, y


def _legend(items):
    return '<div class="legend">' + "".join(
        f'<span><i style="background:{colour}"></i>{escape(name)}</span>' for name, colour in items
    ) + "</div>"


def _line_chart(title, labels, series):
    values = [v for line in series.values() for v in line if v is not None]
    parts, y = _axes(labels, nice_max(max(values, default=0)))
    span = max(len(labels) - 1, 1)

    def x(i):
        return LEFT + (W - LEFT - RIGHT) * i / span

    for i, label in enumerate(labels):
        parts.append(f'<text class="tick" x="{x(i):.1f}" y="{H - 10}" text-anchor="middle">{escape(label)}</text>')
    for name, line in series.items():
        colour = config.SERIES_COLOURS[name]
        run = []
        for i, v in enumerate(list(line) + [None]):       # the trailing None flushes the last run
            if v is None:
                if len(run) > 1:
                    parts.append(f'<polyline fill="none" stroke="{colour}" stroke-width="3" '
                                 f'stroke-linejoin="round" points="{" ".join(run)}"/>')
                run = []
            else:
                run.append(f"{x(i):.1f},{y(v):.1f}")
                parts.append(f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="3" fill="{colour}"/>')
    svg = f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{escape(title)}">{"".join(parts)}</svg>'
    legend = _legend([(name, config.SERIES_COLOURS[name]) for name in series])
    return f'<div class="card"><h3>{escape(title)}</h3>{svg}{legend}</div>'


def _stacked_bars(title, labels, series):
    totals = [sum(values[i] for _, values in series) for i in range(len(labels))]
    parts, y = _axes(labels, nice_max(max(totals, default=0)))
    slot = (W - LEFT - RIGHT) / max(len(labels), 1)
    bar = slot * 0.62
    for i, label in enumerate(labels):
        centre = LEFT + slot * (i + 0.5)
        parts.append(f'<text class="tick" x="{centre:.1f}" y="{H - 10}" text-anchor="middle">{escape(label)}</text>')
        base = 0
        for (name, values), colour in zip(series, config.TREND_COLOURS):
            if values[i]:
                top_y, bottom_y = y(base + values[i]), y(base)
                parts.append(f'<rect x="{centre - bar / 2:.1f}" y="{top_y:.1f}" width="{bar:.1f}" '
                             f'height="{bottom_y - top_y:.1f}" fill="{colour}">'
                             f'<title>{escape(name)}: {values[i]}</title></rect>')
                base += values[i]
    svg = f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{escape(title)}">{"".join(parts)}</svg>'
    return svg + _legend([(name, colour) for (name, _), colour in zip(series, config.TREND_COLOURS)])


def _header(report, logo_b64):
    logo = (f'<img src="data:image/png;base64,{logo_b64}" alt="New Murchison Gold Limited">'
            if logo_b64 else '<span class="wordmark">NMG</span>')
    return (f'<header><div class="wrap">{logo}<div><h1>Health &amp; Safety Performance</h1>'
            f'<p>New Murchison Gold Limited</p></div><div class="month">'
            f'<strong>{escape(report["month_label"])}</strong>'
            f'<p>Data as at {escape(report["generated"])}</p></div></div></header>')


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
    blocks = []
    for name in config.BUCKETS:
        tiles = "".join(f'<div class="tile"><b>{escape(value)}</b><span>{escape(label)}</span></div>'
                        for label, value in report["kpis"][name])
        blocks.append(f'<div class="bucket"><h3 style="background:{config.SERIES_COLOURS[name]}">'
                      f'{escape(name)}</h3>{tiles}</div>')
    return (f'<section id="kpis"><h2>Key indicators</h2><div class="pad">{"".join(blocks)}'
            '<p class="note">TRIFR and LTIFR are rolling 12-month rates per million hours worked.</p>'
            "</div></section>")


def _table(report):
    month = escape(report["month_label"].split(" ")[0])
    heads = "".join(f'<th colspan="2">{escape(name)}</th>' for name in config.BUCKETS)
    subs = "".join(f"<th>{month}</th><th>FYTD</th>" for _ in config.BUCKETS)
    body = "".join(
        ('<tr class="bold">' if row["bold"] else "<tr>")
        + f'<th scope="row">{escape(row["label"])}</th>'
        + "".join(f"<td>{escape(cell)}</td>" for cell in row["cells"]) + "</tr>"
        for row in report["table"])
    return ('<section id="event-table"><h2>Events &mdash; month and financial year to date</h2>'
            f'<div class="scroll"><table><thead><tr><th></th>{heads}</tr>'
            f"<tr><th>Event</th>{subs}</tr></thead><tbody>{body}</tbody></table></div>"
            '<div class="pad"><p class="note">Frequency rates in the FYTD columns are rolling '
            "12-month rates. Head count is NMG employees only, at month end. FYTD runs from 1 July."
            "</p></div></section>")


def _trends(report):
    trend = report["trend"]
    charts = (_line_chart("TRIFR 12 Month Trend", trend["labels"], trend["trifr"])
              + _line_chart("LTIFR 12 Month Trend", trend["labels"], trend["ltifr"]))
    return ('<section id="rate-trends"><h2>Total recordable injury &amp; lost time injury '
            f'frequency rates</h2><div class="pad"><div class="cols">{charts}</div>'
            '<p class="note">Total Recordable Injury Frequency Rate (TRIFR) and Lost Time Injury '
            "Frequency Rate (LTIFR) are calculated over 12 months. They represent the number of "
            "injuries per one million hours worked.</p></div></section>")


def _event_trend(report):
    trend = report["event_trend"]
    head = "".join(f"<th>{escape(label)}</th>" for label in trend["labels"])
    rows = "".join(f'<tr><th scope="row">{escape(name)}</th>'
                   + "".join(f"<td>{value or '–'}</td>" for value in values) + "</tr>"
                   for name, values in trend["series"])
    return ('<section id="event-trend"><h2>Events by type &mdash; last 12 months</h2>'
            f'<div class="pad">{_stacked_bars("Events by type", trend["labels"], trend["series"])}'
            f'<details><summary>Show the numbers</summary><div class="scroll"><table><thead>'
            f"<tr><th>Type</th>{head}</tr></thead><tbody>{rows}</tbody></table></div></details>"
            '<p class="note">Mining and Exploration combined.</p></div></section>')


def _injuries(report):
    cards = []
    for title, items in report["injury_analysis"]:
        longest = max((n for _, n in items), default=1)
        bars = "".join(
            f'<span>{escape(label)}</span><span class="track"><span class="fill" '
            f'style="display:block;width:{n / longest * 100:.0f}%"></span></span>'
            f'<span class="n">{n}</span>' for label, n in items)
        inner = f'<div class="bars">{bars}</div>' if items else \
            '<p class="note">No injuries recorded in the last 12 months.</p>'
        cards.append(f'<div class="card"><h3>{escape(title)}</h3>{inner}</div>')
    return ('<section id="injury-analysis"><h2>Injury analysis &mdash; last 12 months</h2>'
            f'<div class="pad"><div class="cols">{"".join(cards)}</div></div></section>')


def _status(report):
    status = report["status"]
    tiles = "".join(f'<div class="tile stat"><b>{status[key]}</b><span>{label}</span></div>' for key, label in (
        ("events_open", "Events open (12 months)"),
        ("events_closed", "Events closed (12 months)"),
        ("actions_open", "Actions open"),
        ("actions_overdue", "Actions overdue"),
        ("actions_closed_month", "Actions closed in month")))
    return ('<section id="status"><h2>Open events and corrective actions</h2>'
            f'<div class="pad"><div class="bucket">{tiles}</div></div></section>')


def _footer():
    return ("<footer><p><strong>Source:</strong> PeopleTray. Rebuilt daily.</p>"
            "<p><strong>Mining:</strong> all CPO workgroups, Contractors &ndash; Local and "
            "Contractors &ndash; Other. <strong>Exploration:</strong> all GG workgroups and "
            "Drilling Contractors. Perth office and Flight/Accommodation Only are excluded.</p>"
            "<p><strong>Recordable injuries</strong> are lost time, restricted work and medically "
            "treated injuries. Non work related and pre-existing conditions are not counted.</p></footer>")


def render(report, logo_b64=None):
    main = "".join((_notice(report), _kpis(report), _table(report), _trends(report),
                    _event_trend(report), _injuries(report), _status(report), _footer()))
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>NMG Health &amp; Safety Performance</title><style>{CSS}</style></head><body>"
            f'{_header(report, logo_b64)}<div class="wrap">{main}</div></body></html>')
