"""The rules Neil set for the NMG OHS dashboard. No I/O and no arithmetic here."""
import re

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


def injury_code(injury_type):
    """'FAI (First Aid Injury) ' -> 'FAI'; None when the text does not start with a known code."""
    match = re.match(r"[A-Za-z]+", (injury_type or "").strip())
    code = match.group().upper() if match else ""
    return code if code in _INJURY_CODES else None


def classify_injury(injury_type, sub_type):
    """PeopleTray's injury type decides; a blank or unknown one falls back to the sub-type."""
    return injury_code(injury_type) or _SUBTYPE_CLASS.get((sub_type or "").strip().lower(), UNCLASSIFIED)


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


# PeopleTray's own "Open Workflows" chart names open safety events like this.
SAFETY_EVENTS_WORKFLOW = "Safety Events"
# Left off the Open workflows pie: two HR forms PeopleTray's chart does not show either, and
# the Exploration Daily Prestart, which Neil asked to have removed (2026-10-12), and the light
# vehicle prestart (2026-10-22) - "Prestart - Light Vehicles" in the API, "Light Vehicle
# Prestarts" on PeopleTray's own chart.
WORKFLOWS_NOT_CHARTED = ("Uniform Order", "Medical Declaration Form", "Exploration Daily Prestart",
                         "Prestart - Light Vehicles", "Light Vehicle Prestarts")

# Leading indicators (Neil, 2026-10-21): near misses are events, hazards are this PeopleTray form.
HAZARD_REPORT_FORM = "Hazard Report Form"
REPORTING_SERIES = ("Near misses", "Hazard reports")

NAVY, RIVER, GOLD, PALE_GOLD = "#083045", "#55848A", "#927128", "#B19045"
SAND, COOL_GREY, BLACK = "#F1DCAA", "#DBDBD3", "#333334"
SERIES_COLOURS = {MINING: NAVY, EXPLORATION: GOLD}

TREND_GROUPS = ("Injury", NEAR_MISS_ROW, "Property Damage / Loss",
                "Procedural Compliance", "Production Loss", "Other")
TREND_COLOURS = (NAVY, RIVER, GOLD, "#D8C8A2", "#8498A2", "#99999A")

# The open incidents table shows this many, most overdue first (Neil, 2026-10-19).
OPEN_INCIDENTS_SHOWN = 15

# Ozland's ERT obligation (Neil, 2026-10-19): 2 qualified ERT members on day shift and 2 on night
# shift, every day. Qualified = Competent in all six ERT dial competencies, as on the ERT dashboard.
OZLAND_EMPLOYER = "ozland"          # matched inside the person's employer, case-insensitive
ERT_WORK_ROLE = "ERT Member"
ERT_QUALIFICATIONS = ("HLTAID014", "PUASAR024", "RIIERR201E", "PUAFIR207", "PUAFIR306", "PUASAR032")
OZLAND_ERT_PER_SHIFT = 2

# The Emergency Response section is the NMG CPO ERT dashboard itself (Neil, 2026-10-22), shown in a
# frame. Both sites are on neil-noble.github.io, so this page can size the frame to fit.
ERT_SITE_URL = "https://neil-noble.github.io/nmg-ert-site/"
