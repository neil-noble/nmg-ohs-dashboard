"""The rules Neil set for the NMG OHS dashboard. No I/O and no arithmetic here."""

FY_START_MONTH = 7
NMG_EMPLOYER = "New Murchison Gold Ltd"

MINING, EXPLORATION = "Mining", "Exploration"
BUCKETS = (MINING, EXPLORATION)
EXCLUDED, UNMAPPED = "excluded", "unmapped"

# (result, workgroup prefixes, exact workgroup names). Decided by Neil 2026-10-11.
_BUCKET_RULES = (
    (MINING, ("CPO - ",), ("Contractors - Local", "Contractors - Other")),
    (EXPLORATION, ("GG - ",), ("Drilling Contractors",)),
    (EXCLUDED, ("PER - ",), ("Flight/Accommodation ONLY",)),
)


def bucket(workgroup):
    name = (workgroup or "").strip()
    for result, prefixes, exact in _BUCKET_RULES:
        if name in exact or name.startswith(prefixes):
            return result
    return UNMAPPED


INJURY_TYPE = "Injury"
INJURY_CLASSES = (
    ("LTI", "Lost Time Injury"),
    ("RWI", "Restricted Work Injury"),
    ("MTI", "Medically Treated Injury"),
    ("FAI", "First Aid Injury"),
    ("NT", "No Treatment Injury"),
)
RECORDABLE = ("LTI", "RWI", "MTI")
NOT_COUNTED = ("NWR", "PEC")      # non work related, pre-existing condition
UNCLASSIFIED = "Unclassified injury"

_INJURY_CODES = tuple(code for code, _ in INJURY_CLASSES) + NOT_COUNTED
_SUBTYPE_CLASS = {
    "lost time injury": "LTI",
    "restricted work injury": "RWI",
    "medical treatment injury": "MTI",
    "first aid injury": "FAI",
    "no treatment required": "NT",
}


def classify_injury(injury_type, sub_type):
    """PeopleTray's injury type decides; a blank or unknown one falls back to the sub-type."""
    code = (injury_type or "").strip().split(" ")[0].upper()
    if code in _INJURY_CODES:
        return code
    return _SUBTYPE_CLASS.get((sub_type or "").strip().lower(), UNCLASSIFIED)


NEAR_MISS_ROW = "Near Miss"
ENVIRONMENT_ROW = "Environmental Incidents"
SECURITY_ROW = "Security Incident / Violence"
HIDDEN_EVENT_TYPES = ("Non Work Related",)
FIXED_EVENT_ROWS = (
    ENVIRONMENT_ROW,
    "Production Loss",
    "Procedural Compliance",
    "Property Damage / Loss",
    SECURITY_ROW,
    "Business / Operational Interruption",
    "Misfire",
    "Community / Heritage",
)


def event_row(event_type):
    """Table row a non-injury event counts under; None for types the report does not show."""
    name = (event_type or "").strip()
    if name in HIDDEN_EVENT_TYPES:
        return None
    if name in ("Violence", "Security"):
        return SECURITY_ROW
    if "environment" in name.lower():
        return ENVIRONMENT_ROW
    return name or "Unspecified event type"


NAVY, RIVER, GOLD, PALE_GOLD = "#083045", "#55848A", "#927128", "#B19045"
SAND, COOL_GREY, BLACK = "#F1DCAA", "#DBDBD3", "#333334"
SERIES_COLOURS = {MINING: NAVY, EXPLORATION: GOLD}

TREND_GROUPS = ("Injury", NEAR_MISS_ROW, "Property Damage / Loss",
                "Procedural Compliance", "Production Loss", "Other")
TREND_COLOURS = (NAVY, RIVER, GOLD, "#D8C8A2", "#8498A2", "#99999A")
