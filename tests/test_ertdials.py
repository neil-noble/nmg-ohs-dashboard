import io

import pytest

import ertdials


def dial(label, count, minimum):
    return (f'<div class="gauge-cell"><svg viewBox="0 0 200 172"><path d="M 1 1"/>'
            f'<text x="100" y="94" font-size="40" font-weight="700">{count}</text>'
            f'<text x="100" y="120" font-size="13">min {minimum} per 24hr</text>'
            f'<text x="100" y="165" font-size="13">{label}</text></svg></div>')


def row(ident, dials):
    return f'<div class="gauges" id="{ident}-gauges">{"".join(dials)}</div>'


PAGE = ("<p>Last updated: 19 Oct 2026, 11:38 AM AWST</p>"
        + row("day", [dial("Advanced First Aid", 4, 2), dial("Fire &amp; Rescue", 1, 4)])
        + row("night", [dial("HAZMAT", 1, 4)])
        + row("total", [dial("HAZMAT", 2, 4)])
        + '<div><svg><text font-size="40">99</text></svg></div>')     # a later chart, not a dial


def test_reads_each_row_of_dials():
    assert ertdials.parse_ert_page(PAGE) == {
        "updated": "19 Oct 2026, 11:38 AM AWST",
        "rows": [("Day shift", [("Advanced First Aid", 4, 2), ("Fire & Rescue", 1, 4)]),
                 ("Night shift", [("HAZMAT", 1, 4)]),
                 ("Day and night", [("HAZMAT", 2, 4)])]}


def test_a_missing_or_empty_row_is_an_error():
    with pytest.raises(ertdials.ErtDialsError, match="night shift"):
        ertdials.parse_ert_page(PAGE.replace('id="night-gauges"', 'id="other"'))
    with pytest.raises(ertdials.ErtDialsError, match="no dials"):
        ertdials.parse_ert_page(PAGE.replace(dial("HAZMAT", 2, 4), ""))


def test_a_failed_download_is_an_ert_error():
    def opener(url, timeout):
        raise OSError("down")
    with pytest.raises(ertdials.ErtDialsError, match="OSError"):
        ertdials.fetch_ert_dials(opener)


def test_download_is_parsed():
    def opener(url, timeout):
        assert url == ertdials.ERT_URL
        return io.BytesIO(PAGE.encode("utf-8"))
    assert ertdials.fetch_ert_dials(opener)["rows"][1] == ("Night shift", [("HAZMAT", 1, 4)])
