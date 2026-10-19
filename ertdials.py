"""Read the ERT competency dials off the NMG CPO ERT dashboard.

Neil asked (2026-10-19) for the Emergency Services list to use "the data from NMG CPO ERT
dashboard", so the dials are read off that public page rather than worked out again here: it
already applies the roster, shift and PPE-hold rules. Each dial is one competency, the number of
ERT members on the roster who hold it, and its minimum.
"""
import html
import re
import urllib.request

ERT_URL = "https://neil-noble.github.io/nmg-ert-site/"
# The ERT page's three dial rows, by the id of the row and the name shown here.
ROWS = (("day", "Day shift"), ("night", "Night shift"), ("total", "Day and night"))
# Each dial is an inline SVG in its own cell; a row is the run of cells after its opening tag.
_CELL = re.compile(r'\s*<div class="gauge-cell">(<svg\b.*?</svg>)</div>', re.S)
_COUNT = re.compile(r'font-size="40"[^>]*>(\d+)</text>')
_MINIMUM = re.compile(r'>min (\d+) per [^<]*</text>')
_TEXT = re.compile(r'<text[^>]*>([^<]*)</text>')
_UPDATED = re.compile(r'Last updated:\s*([^<]*?)\s*</')


class ErtDialsError(RuntimeError):
    """The ERT dashboard could not be read."""


def parse_ert_page(page):
    """{"updated": str, "rows": [(shift, [(competency, held, minimum), ...]), ...]}."""
    rows = []
    for ident, shift in ROWS:
        marker = f'id="{ident}-gauges">'
        at = page.find(marker)
        if at < 0:
            raise ErtDialsError(f"the {shift.lower()} dials are not on the ERT page")
        at += len(marker)
        svgs = []
        while cell := _CELL.match(page, at):
            svgs.append(cell.group(1))
            at = cell.end()
        dials = []
        for svg in svgs:
            count, minimum, texts = _COUNT.search(svg), _MINIMUM.search(svg), _TEXT.findall(svg)
            if not (count and minimum and texts):
                raise ErtDialsError(f"a {shift.lower()} dial could not be read")
            dials.append((html.unescape(texts[-1]).strip(), int(count.group(1)), int(minimum.group(1))))
        if not dials:
            raise ErtDialsError(f"the {shift.lower()} row has no dials")
        rows.append((shift, dials))
    updated = _UPDATED.search(page)
    return {"updated": html.unescape(updated.group(1)) if updated else "", "rows": rows}


def fetch_ert_dials(opener=urllib.request.urlopen):
    """The dials, or raises ErtDialsError. The page is public, so no key is involved."""
    try:
        with opener(ERT_URL, timeout=60) as response:
            page = response.read().decode("utf-8")
    except (OSError, ValueError) as error:
        raise ErtDialsError(f"could not read the ERT dashboard: {type(error).__name__}") from None
    return parse_ert_page(page)
