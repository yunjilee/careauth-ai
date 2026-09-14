"""Configuration and fixture identifiers for the seeding pipeline.

Every code system below is a demo system owned by this project. Real licensed
code sets (CPT, InterQual, MCG) are deliberately avoided; the MVP only needs a
stable identifier for "routine lumbar MRI without contrast".
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

FHIR_BASE_URL = os.environ.get("FHIR_BASE_URL", "http://localhost:8080/fhir")
DATA_DIR = Path(os.environ.get("CAREAUTH_DATA_DIR", "./data")).resolve()
DOCUMENT_DIR = DATA_DIR / "documents"
LABEL_DIR = DATA_DIR / "labels"

# Documents are served by the application behind an authorized endpoint, never
# as a raw file path. DocumentReference.content.attachment.url points here.
DOCUMENT_ENDPOINT = os.environ.get(
    "CAREAUTH_DOCUMENT_ENDPOINT", "https://careauth.local/api/documents"
)

BASE_SYSTEM = "https://careauth.example/demo"
PATIENT_ID_SYSTEM = f"{BASE_SYSTEM}/patient-id"
ORDER_ID_SYSTEM = f"{BASE_SYSTEM}/order-id"
DOCUMENT_ID_SYSTEM = f"{BASE_SYSTEM}/document-id"
MEMBER_ID_SYSTEM = f"{BASE_SYSTEM}/member-id"
PROCEDURE_SYSTEM = f"{BASE_SYSTEM}/procedure"
NOTE_TYPE_SYSTEM = f"{BASE_SYSTEM}/note-type"
CONDITION_SYSTEM = f"{BASE_SYSTEM}/condition"

DEMO_PROCEDURE_CODE = "LUMBAR-MRI-NO-CONTRAST"
DEMO_PROCEDURE_DISPLAY = "Routine lumbar spine MRI without contrast"

# Synthea's shipped payer files name real insurers. These fictional payers
# replace them before generation so no real insurer name reaches the fixtures.
PAYERS = {
    "cedar": {
        "id": "910000",
        "name": "Cedar Demo Health",
        "plans": {"cedar-standard": {"id": "910001", "name": "Cedar Standard"}},
    },
    "larkspur": {
        "id": "920000",
        "name": "Larkspur Demo Assurance",
        "plans": {"larkspur-select": {"id": "920001", "name": "Larkspur Select"}},
    },
    "northgate": {
        "id": "930000",
        "name": "Northgate Demo Plan",
        "plans": {"northgate-essential": {"id": "930001", "name": "Northgate Essential"}},
    },
}

# Two provider organizations exist only so cross-organization access attempts
# are testable. HAPI does not isolate them; the adapter must.
ORGANIZATIONS = {
    "juniper": {"id": "org-juniper", "name": "Juniper Specialty Care"},
    "summit": {"id": "org-summit", "name": "Summit Demo Orthopedics"},
}

PRACTITIONERS = {
    "nguyen": {"id": "prac-nguyen", "family": "Nguyen", "given": "Dana", "org": "juniper"},
    "okafor": {"id": "prac-okafor", "family": "Okafor", "given": "Ijeoma", "org": "juniper"},
    "reyes": {"id": "prac-reyes", "family": "Reyes", "given": "Marta", "org": "summit"},
}

# The fictional Cedar Standard policy the example in the README describes.
REQUIREMENTS = {
    "REQ-ORDER": "Signed imaging order from the treating clinician",
    "REQ-EXAM": "Examination documented within the policy lookback period",
    "REQ-CONSERVATIVE": "Completed conservative-treatment course of at least six weeks",
}

EXAM_LOOKBACK_DAYS = 90
CONSERVATIVE_MIN_WEEKS = 6

# Fixed seed keeps the evaluation population regenerable. Changing it orphans
# every hand-checked gold label.
SYNTHEA_SEED = 20260914
REFERENCE_TODAY = date(2026, 10, 1)
