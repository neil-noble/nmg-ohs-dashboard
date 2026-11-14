"""The roster-reading tripwire (roster_check.py). Do not delete or weaken - Neil, 2026-11-14.

Same file in every NMG project that reads the PeopleTray roster.
"""
import importlib.util
import unittest
from datetime import date
from pathlib import Path


def _load():
    here = Path(__file__).resolve().parent
    packages = sorted(p.parent for p in here.parent.glob("*/roster_check.py") if p.parent.name != "tests")
    for folder in (here, here.parent, *packages):
        if (folder / "roster_check.py").is_file():
            spec = importlib.util.spec_from_file_location("roster_check", folder / "roster_check.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    raise FileNotFoundError("roster_check.py")


rc = _load()
DAY = date(2026, 11, 14)
DS, NS, TR, FIA_NS = 1, 2, 3, 4


def shift(type_id, name, day=False, night=False, offsite=False):
    return {"id": type_id, "statusName": name, "isDayshift": day, "isNightshift": night, "isOffsite": offsite}


TYPES = {DS: shift(DS, "Dayshift", day=True), NS: shift(NS, "Nightshift", night=True),
         TR: shift(TR, "Training - Offsite", day=True, offsite=True),
         FIA_NS: shift(FIA_NS, "Fly in AM - Nightshift", night=True)}


def row(person=1, shift_id=DS, day="2026-11-14T00:00:00", **extra):
    return {"personId": person, "shiftTypeId": shift_id, "rosterDate": day,
            "lastName": "TEST", "firstName": f"Person{person}", **extra}


class GoodRosterPasses(unittest.TestCase):
    def test_a_clean_day_passes(self):
        rc.verify([row(1), row(2, NS), row(3, None)], TYPES, DAY)

    def test_exact_duplicate_rows_pass(self):
        # PeopleTray repeats a person's row once per workgroup folder.
        rc.verify([row(1), row(1), row(2, NS)], TYPES, DAY)

    def test_a_week_passes_and_ids_may_be_strings(self):
        rows = [row(1, str(DS), "2026-11-14T00:00:00"), row(1, NS, "2026-11-20T00:00:00")]
        rc.verify(rows, list(TYPES.values()), DAY, date(2026, 11, 20))

    def test_change_line_over_base_line(self):
        rc.verify([row(1, NS, baseShiftTypeId=DS, changeShiftTypeId=NS),
                   row(2, DS, baseShiftTypeId=DS, changeShiftTypeId=None)], TYPES, DAY)


class BadRosterIsRefused(unittest.TestCase):
    def refused(self, text, *args, **kwargs):
        with self.assertRaises(rc.RosterError) as caught:
            rc.verify(*args, **kwargs)
        self.assertIn(text, str(caught.exception))

    def test_empty_or_wrong_shape(self):
        self.refused("no roster rows", [], TYPES, DAY)
        self.refused("no roster rows", {"error": "x"}, TYPES, DAY)
        self.refused("no shift types", [row()], {}, DAY)

    def test_a_row_for_another_day(self):
        self.refused("2026-11-13", [row(), row(2, day="2026-11-13T00:00:00")], TYPES, DAY)
        self.refused("(no date)", [row(day=None)], TYPES, DAY)

    def test_two_different_shifts_on_one_day(self):
        self.refused("TEST Person1 has two different shifts on 2026-11-14", [row(1, DS), row(1, NS)], TYPES, DAY)
        self.refused("two different shifts", [row(1, DS), row(1, None)], TYPES, DAY)

    def test_a_shift_type_peopletray_does_not_list(self):
        self.refused("shift type 99 is not in PeopleTray's shift types", [row(1, 99)], TYPES, DAY)

    def test_a_shift_type_without_flags_or_flagged_both(self):
        types = {**TYPES, 7: {"id": 7, "statusName": "Mystery"}, 8: shift(8, "Both", day=True, night=True)}
        self.refused("'Mystery' has no true/false", [row(1, 7)], types, DAY)
        self.refused("'Both' is flagged both day and night", [row(1, 8)], types, DAY)

    def test_shift_type_id_that_is_not_the_change_line(self):
        self.refused("is not the change/base shift", [row(1, DS, baseShiftTypeId=DS, changeShiftTypeId=NS)], TYPES, DAY)

    def test_only_the_people_who_matter_can_stop_the_run(self):
        rows = [row(1), row(2, DS), row(2, NS), row(3, 99)]
        rc.verify(rows, TYPES, DAY, person_ids={1})
        self.refused("two different shifts", rows, TYPES, DAY, person_ids={1, 2})

    def test_public_logs_get_ids_not_names(self):
        with self.assertRaises(rc.RosterError) as caught:
            rc.verify([row(1, DS), row(1, NS)], TYPES, DAY, name_people=False)
        self.assertIn("person id 1", str(caught.exception))
        self.assertNotIn("TEST", str(caught.exception))


class DayOrNightComesFromTheFlags(unittest.TestCase):
    def test_flags_decide_never_the_code_or_the_name(self):
        self.assertEqual(rc.shift_kind(TYPES[DS]), "day")
        self.assertEqual(rc.shift_kind(TYPES[NS]), "night")
        self.assertEqual(rc.shift_kind(TYPES[FIA_NS]), "night")      # FIA is usually a day code
        self.assertIsNone(rc.shift_kind(TYPES[TR]))                  # flagged day shift, but off site
        self.assertIsNone(rc.shift_kind({"statusName": "Nightshift"}))   # a name is not a flag
        self.assertIsNone(rc.shift_kind(None))


if __name__ == "__main__":
    unittest.main()
