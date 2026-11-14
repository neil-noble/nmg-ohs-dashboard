# NMG OHS Dashboard
domain: New Murchison Gold | health & safety statistics dashboard | PeopleTray API
env: python stdlib + pyyaml + pytest; eomhours.py also needs playwright (chromium) + openpyxl (imported only when filling a month - versions pinned in the workflow)
load: state.yaml
hours_rule: rates must match the EOM report - months EOM has sent use its frozen hours + injury counts (nmg-eom data/history.yaml); later months use the PeopleTray exposurehours feed; a finished month the feed lacks takes hours from the web End of Month Report via eomhours.py (EOM rules copied from NMG EOM eom/hours.py + eom/config.py - keep in step); feed wins once it has the month (Neil 2026-11-07)

## PeopleTray roster rules - never break (Neil 2026-11-14, mission critical: people rely on this in an emergency)
- Every roster read passes roster_check.verify() before anything is built or sent. A read it refuses (wrong day, unknown or unflagged shift type, a person with two different shifts) STOPS the run - never resolve it silently.
- The shift is shiftTypeId (the Change line over the Base line). Never baseShiftTypeId alone.
- Day / night / off site come from the shift type's isDayshift / isNightshift / isOffsite flags (roster_check.shift_kind). Never from a status code or words in the shift name - PeopleTray shares codes (FIA is both "Fly in AM - Dayshift" and "Fly in AM - Nightshift").
- A shift flagged off site is never a day or night shift on site.
- A Shift Type column in a PeopleTray web export is never trusted; the roster API decides.
- roster_check.py is identical in every NMG project (copy of record: C:\claude\NMG Evacuation List\reference\roster_check.py). Its tests and the test_roster_rules tests must not be deleted or weakened; a change to shift logic needs a failing test first.
