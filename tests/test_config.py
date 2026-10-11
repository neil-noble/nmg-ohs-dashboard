import pytest

import config


@pytest.mark.parametrize("workgroup, expected", [
    ("CPO - Ozland", config.MINING),
    ("CPO - Management - Contractors/Visitors", config.MINING),
    ("Contractors - Local", config.MINING),
    ("Contractors - Other", config.MINING),
    ("GG - Exploration", config.EXPLORATION),
    ("GG - Exploration Contractors", config.EXPLORATION),
    ("Drilling Contractors", config.EXPLORATION),
    ("Flight/Accommodation ONLY", config.EXCLUDED),
    ("PER - Finance", config.EXCLUDED),
    ("  CPO - Geology  ", config.MINING),
    ("Shutdown Crew", config.UNMAPPED),
    ("", config.UNMAPPED),
    (None, config.UNMAPPED),
])
def test_bucket(workgroup, expected):
    assert config.bucket(workgroup) == expected


@pytest.mark.parametrize("injury_type, sub_type, expected", [
    ("LTI (Lost Time Injury) ", "Medical Treatment Injury", "LTI"),   # injury type wins
    ("FAI (First Aid Injury) ", "No Treatment Required", "FAI"),
    ("", "First Aid Injury", "FAI"),                                  # blank falls back
    (None, "No Treatment Required", "NT"),
    (None, "Medical Treatment Injury", "MTI"),
    (None, "Restricted Work Injury", "RWI"),
    (None, "Lost Time Injury", "LTI"),
    ("NWR (Non Work Related) ", "No Treatment Required", "NWR"),
    ("PEC (Pre-Existing Condition) ", "First Aid Injury", "PEC"),
    ("mti (medical treatment injury)", None, "MTI"),
    ("", "", config.UNCLASSIFIED),
    ("Something new", "Something else", config.UNCLASSIFIED),
])
def test_classify_injury(injury_type, sub_type, expected):
    assert config.classify_injury(injury_type, sub_type) == expected


@pytest.mark.parametrize("event_type, expected", [
    ("Near Miss", "Near Miss"),
    ("Violence", "Security Incident / Violence"),
    ("Security", "Security Incident / Violence"),
    ("Environmental Incident", "Environmental Incidents"),
    ("Property Damage / Loss", "Property Damage / Loss"),
    ("Non Work Related", None),
    ("Brand New Type", "Brand New Type"),
    ("", "Unspecified event type"),
    (None, "Unspecified event type"),
])
def test_event_row(event_type, expected):
    assert config.event_row(event_type) == expected
