"""Refuse a PeopleTray roster read that cannot be trusted. Same file in every NMG project.

Neil, 2026-11-14 (mission critical - people rely on these rosters in an emergency):
there must be no errors reading the PeopleTray roster. A roster is only used once
verify() has passed; anything it cannot vouch for stops the run with a message
saying what is wrong, instead of being quietly resolved one way or the other.

The rules every NMG project reads the roster by:

1. The shift is `shiftTypeId` - PeopleTray's effective shift, the Change line over
   the Base line. Never `baseShiftTypeId` on its own.
2. Day shift / night shift / off site come from the shift type's own flags
   (isDayshift, isNightshift, isOffsite). Never from a status code or from words in
   the shift name: codes are shared (FIA is both "Fly in AM - Dayshift" and
   "Fly in AM - Nightshift"; FIP, DIP, DIL, FOA and DOP are shared too).
3. A shift flagged off site is never a day or night shift on site.
4. A Shift Type column in a PeopleTray web export is never trusted (it goes stale);
   the roster API decides.

verify() is the tripwire behind those rules. It raises RosterError when:

* the roster or the shift types are missing, empty or the wrong shape
* a row is dated outside the day(s) that were asked for
* a row's shiftTypeId is not what its change/base lines say it should be
* a person who matters has a shift type PeopleTray does not list, or one without
  true/false day, night and off-site flags, or one flagged both day and night
* a person who matters has two different shifts on the same day

Copy of record: C:\\claude\\NMG Evacuation List\\reference\\roster_check.py. Keep the copies identical.
"""
from datetime import date

FLAGS = ("isDayshift", "isNightshift", "isOffsite")


class RosterError(RuntimeError):
    """The PeopleTray roster read cannot be trusted. Do not build or send anything from it."""


def _as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


def _day(value):
    return value.isoformat() if isinstance(value, date) else str(value)[:10]


def shift_kind(shift_type):
    """"day", "night" or None for a PeopleTray shift type - on site only (rules 2 and 3)."""
    shift_type = shift_type or {}
    if shift_type.get("isOffsite"):
        return None
    if shift_type.get("isNightshift"):
        return "night"
    if shift_type.get("isDayshift"):
        return "day"
    return None


def verify(roster, shift_types, first_day, last_day=None, person_ids=None, name_people=True):
    """Raise RosterError unless `roster` is a trustworthy read for first_day..last_day.

    shift_types: {id: shift type} or a list of shift types.
    person_ids:  the people whose shifts will be used (None = everyone on the roster).
                 Row-level checks apply to them only, so someone else's bad row
                 cannot stop a run that never reads it.
    name_people: False where the run log is public - people are then given by id.
    """
    first, last = _day(first_day), _day(last_day if last_day is not None else first_day)
    if not isinstance(roster, list) or not roster:
        raise RosterError(f"PeopleTray returned no roster rows for {first}" + (f" to {last}" if last != first else "") + ".")
    if isinstance(shift_types, list):
        shift_types = {s.get("id"): s for s in shift_types if isinstance(s, dict)}
    if not isinstance(shift_types, dict) or not shift_types:
        raise RosterError("PeopleTray returned no shift types.")
    types = {_as_int(key): value for key, value in shift_types.items()}
    wanted = None if person_ids is None else {_as_int(p) for p in person_ids}

    def who(row):
        if name_people and (row.get("lastName") or row.get("firstName")):
            return f"{str(row.get('lastName') or '').strip()} {str(row.get('firstName') or '').strip()}".strip()
        return f"person id {row.get('personId')}"

    problems, shifts = [], {}
    for row in roster:
        if not isinstance(row, dict):
            raise RosterError(f"PeopleTray roster rows are not records ({type(row).__name__}).")
        day = _day(row.get("rosterDate") or "")
        if not first <= day <= last:
            raise RosterError(f"PeopleTray returned a roster row dated {day or '(no date)'}; "
                              f"{first}" + (f" to {last}" if last != first else "") + " was asked for.")
        shift_id = _as_int(row.get("shiftTypeId"))
        if "baseShiftTypeId" in row or "changeShiftTypeId" in row:
            expected = _as_int(row.get("changeShiftTypeId") or row.get("baseShiftTypeId"))
            if shift_id != expected:
                problems.append(f"{who(row)} on {day}: shiftTypeId {shift_id} is not the change/base shift {expected}")
        if wanted is not None and _as_int(row.get("personId")) not in wanted:
            continue
        key = (_as_int(row.get("personId")), day)
        if key in shifts and shifts[key][0] != shift_id:
            problems.append(f"{who(row)} has two different shifts on {day}")
        shifts.setdefault(key, (shift_id, row))
        if shift_id is None:
            continue                                    # no shift that day
        shift_type = types.get(shift_id)
        if not isinstance(shift_type, dict):
            problems.append(f"{who(row)} on {day}: shift type {shift_id} is not in PeopleTray's shift types")
        elif not all(isinstance(shift_type.get(flag), bool) for flag in FLAGS):
            problems.append(f"shift type {shift_type.get('statusName') or shift_id!r} has no true/false "
                            f"{' / '.join(FLAGS)} flags")
        elif shift_type["isDayshift"] and shift_type["isNightshift"]:
            problems.append(f"shift type {shift_type.get('statusName') or shift_id!r} is flagged both day and night shift")
    if problems:
        unique = list(dict.fromkeys(problems))
        more = f" (+{len(unique) - 5} more)" if len(unique) > 5 else ""
        raise RosterError("PeopleTray roster cannot be trusted: " + "; ".join(unique[:5]) + more)
