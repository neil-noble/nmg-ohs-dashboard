"""Month arithmetic. A month is a (year, month) tuple throughout the project."""
import calendar
from datetime import date, datetime, timedelta, timezone

import config

# Perth is UTC+8 all year. A fixed offset avoids needing tzdata on Windows.
PERTH = timezone(timedelta(hours=8))


def today_perth():
    return datetime.now(PERTH).date()


def now_label():
    return datetime.now(PERTH).strftime("%d %b %Y, %H:%M AWST").lstrip("0")


def add_months(ym, n):
    index = ym[0] * 12 + ym[1] - 1 + n
    return (index // 12, index % 12 + 1)


def reporting_month(today):
    return add_months((today.year, today.month), -1)


def fy_start(ym):
    year, month = ym
    return (year if month >= config.FY_START_MONTH else year - 1, config.FY_START_MONTH)


def month_range(first, last):
    months, current = [], first
    while current <= last:
        months.append(current)
        current = add_months(current, 1)
    return months


def rolling_12(ym):
    return month_range(add_months(ym, -11), ym)


def month_end(ym):
    return date(ym[0], ym[1], calendar.monthrange(ym[0], ym[1])[1])


def short_label(ym):
    return f"{calendar.month_abbr[ym[1]]} {ym[0] % 100:02d}"


def long_label(ym):
    return f"{calendar.month_name[ym[1]]} {ym[0]}"


def parse_day(value):
    """PeopleTray sends ISO datetimes in most fields but dd-mm-yyyy in events.eventDate."""
    text = (value or "").strip()
    try:
        if len(text) >= 10 and text[2] == "-" and text[5] == "-":
            return date(int(text[6:10]), int(text[3:5]), int(text[0:2]))
        return date.fromisoformat(text[:10])
    except ValueError:
        return None
