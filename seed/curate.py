"""Curation: author the FHIR resources Synthea does not supply, and pin IDs.

Synthea produces plausible Patient/Condition/Encounter/MedicationRequest history.
It does not produce the case-defining artifacts this workflow depends on, so
those are authored here with deterministic identifiers.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from . import config
from .cases import CaseSpec, Fragment
from .notes import DocumentSpec

Resource = dict[str, Any]
Entry = tuple[Resource, str]


def _instant(day: date) -> str:
    return f"{day.isoformat()}T09:00:00Z"


def build_infrastructure() -> list[Entry]:
    """Payer organizations, provider organizations, and ordering clinicians."""
    entries: list[Entry] = []

    for key, payer in config.PAYERS.items():
        entries.append(
            (
                {
                    "resourceType": "Organization",
                    "id": f"payer-{key}",
                    "identifier": [
                        {"system": f"{config.BASE_SYSTEM}/payer-id", "value": payer["id"]}
                    ],
                    "active": True,
                    "type": [
                        {
                            "coding": [
                                {
                                    "system": "http://terminology.hl7.org/CodeSystem/organization-type",
                                    "code": "ins",
                                    "display": "Insurance Company",
                                }
                            ]
                        }
                    ],
                    "name": payer["name"],
                },
                f"Organization/payer-{key}",
            )
        )

    for key, org in config.ORGANIZATIONS.items():
        entries.append(
            (
                {
                    "resourceType": "Organization",
                    "id": org["id"],
                    "identifier": [
                        {"system": f"{config.BASE_SYSTEM}/org-id", "value": key}
                    ],
                    "active": True,
                    "type": [
                        {
                            "coding": [
                                {
                                    "system": "http://terminology.hl7.org/CodeSystem/organization-type",
                                    "code": "prov",
                                    "display": "Healthcare Provider",
                                }
                            ]
                        }
                    ],
                    "name": org["name"],
                },
                f"Organization/{org['id']}",
            )
        )

    for key, prac in config.PRACTITIONERS.items():
        entries.append(
            (
                {
                    "resourceType": "Practitioner",
                    "id": prac["id"],
                    "active": True,
                    "name": [
                        {
                            "use": "official",
                            "family": prac["family"],
                            "given": [prac["given"]],
                            "prefix": ["Dr."],
                        }
                    ],
                },
                f"Practitioner/{prac['id']}",
            )
        )
        entries.append(
            (
                {
                    "resourceType": "PractitionerRole",
                    "id": f"role-{key}",
                    "active": True,
                    "practitioner": {"reference": f"Practitioner/{prac['id']}"},
                    "organization": {
                        "reference": f"Organization/{config.ORGANIZATIONS[prac['org']]['id']}"
                    },
                },
                f"PractitionerRole/role-{key}",
            )
        )

    return entries


def _patient(case: CaseSpec) -> Resource:
    org_id = config.ORGANIZATIONS[case.org]["id"]
    return {
        "resourceType": "Patient",
        "id": case.case_id,
        "identifier": [
            {
                "use": "usual",
                "system": config.PATIENT_ID_SYSTEM,
                "value": case.case_id,
            }
        ],
        "active": True,
        "name": [{"use": "official", "family": case.family, "given": [case.given]}],
        "gender": case.gender,
        "birthDate": case.birth_date.isoformat(),
        "managingOrganization": {"reference": f"Organization/{org_id}"},
    }


def _coverage(case: CaseSpec) -> Resource:
    payer = config.PAYERS[case.payer]
    plan = payer["plans"][case.plan]
    return {
        "resourceType": "Coverage",
        "id": f"cov-{case.case_id}",
        "identifier": [
            {"system": config.MEMBER_ID_SYSTEM, "value": case.member_id}
        ],
        "status": "active",
        "beneficiary": {"reference": f"Patient/{case.case_id}"},
        "subscriberId": case.member_id,
        "payor": [{"reference": f"Organization/payer-{case.payer}"}],
        "period": {"start": f"{case.service_date.year}-01-01"},
        "class": [
            {
                "type": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/coverage-class",
                            "code": "plan",
                        }
                    ]
                },
                "value": plan["id"],
                "name": plan["name"],
            }
        ],
    }


def _encounter(case: CaseSpec, day: date) -> Resource:
    org_id = config.ORGANIZATIONS[case.org]["id"]
    return {
        "resourceType": "Encounter",
        "id": f"enc-{case.case_id}",
        "status": "finished",
        "class": {
            "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
            "code": "AMB",
            "display": "ambulatory",
        },
        "subject": {"reference": f"Patient/{case.case_id}"},
        "period": {"start": _instant(day), "end": _instant(day)},
        "serviceProvider": {"reference": f"Organization/{org_id}"},
    }


def _condition(case: CaseSpec, onset: date) -> Resource:
    return {
        "resourceType": "Condition",
        "id": f"cond-{case.case_id}",
        "clinicalStatus": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                    "code": "active",
                }
            ]
        },
        "verificationStatus": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                    "code": "confirmed",
                }
            ]
        },
        "code": {
            "coding": [
                {
                    "system": config.CONDITION_SYSTEM,
                    "code": "LUMBAR-RADICULOPATHY",
                    "display": "Lumbar radiculopathy",
                }
            ],
            "text": "Lumbar radiculopathy",
        },
        "subject": {"reference": f"Patient/{case.case_id}"},
        "onsetDateTime": onset.isoformat(),
    }


def _service_request(case: CaseSpec) -> Resource:
    signed = not case.has(Fragment.UNSIGNED_ORDER)
    prac = config.PRACTITIONERS[case.requester]
    resource: Resource = {
        "resourceType": "ServiceRequest",
        "id": case.order_id,
        "identifier": [
            {"system": config.ORDER_ID_SYSTEM, "value": case.order_id}
        ],
        "status": "active" if signed else "draft",
        "intent": "order" if signed else "proposal",
        "category": [
            {
                "coding": [
                    {
                        "system": config.BASE_SYSTEM + "/service-category",
                        "code": "imaging",
                        "display": "Imaging",
                    }
                ]
            }
        ],
        "code": {
            "coding": [
                {
                    "system": config.PROCEDURE_SYSTEM,
                    "code": config.DEMO_PROCEDURE_CODE,
                    "display": config.DEMO_PROCEDURE_DISPLAY,
                }
            ],
            "text": config.DEMO_PROCEDURE_DISPLAY,
        },
        "subject": {"reference": f"Patient/{case.case_id}"},
        "encounter": {"reference": f"Encounter/enc-{case.case_id}"},
        "authoredOn": _instant(case.service_date - timedelta(days=7)),
        "occurrenceDateTime": case.service_date.isoformat(),
        "reasonReference": [{"reference": f"Condition/cond-{case.case_id}"}],
    }
    if signed:
        resource["requester"] = {"reference": f"Practitioner/{prac['id']}"}
    return resource


def _document_reference(case: CaseSpec, doc: DocumentSpec) -> Resource:
    org_id = config.ORGANIZATIONS[case.org]["id"]
    prac = config.PRACTITIONERS[case.requester]
    return {
        "resourceType": "DocumentReference",
        "id": doc.doc_id,
        "identifier": [
            {"system": config.DOCUMENT_ID_SYSTEM, "value": doc.doc_id}
        ],
        "status": "current",
        "docStatus": "final",
        "type": {
            "coding": [
                {
                    "system": config.NOTE_TYPE_SYSTEM,
                    "code": doc.type_code,
                    "display": doc.title,
                }
            ],
            "text": doc.title,
        },
        "subject": {"reference": f"Patient/{case.case_id}"},
        # Upload date. The clinical event date lives in context.period.
        "date": _instant(doc.upload_date),
        "author": [{"reference": f"Practitioner/{prac['id']}"}],
        "custodian": {"reference": f"Organization/{org_id}"},
        "content": [
            {
                "attachment": {
                    "contentType": doc.content_type,
                    "url": f"{config.DOCUMENT_ENDPOINT}/{doc.doc_id}",
                    "title": doc.title,
                    "creation": _instant(doc.clinical_date),
                }
            }
        ],
        "context": {
            "encounter": [{"reference": f"Encounter/enc-{case.case_id}"}],
            "period": {
                "start": _instant(doc.clinical_date),
                "end": _instant(doc.clinical_date),
            },
        },
    }


def build_case_entries(
    case: CaseSpec,
    documents: list[DocumentSpec],
    history: list[Resource] | None = None,
) -> list[Entry]:
    """Full resource set for one case, ready for a transaction bundle."""
    exam_day = case.service_date - timedelta(days=20)
    entries: list[Entry] = [
        (_patient(case), f"Patient/{case.case_id}"),
        (_coverage(case), f"Coverage/cov-{case.case_id}"),
        (_encounter(case, exam_day), f"Encounter/enc-{case.case_id}"),
        (_condition(case, case.service_date - timedelta(days=180)), f"Condition/cond-{case.case_id}"),
        (_service_request(case), f"ServiceRequest/{case.order_id}"),
    ]

    for resource in history or []:
        entries.append((resource, f"{resource['resourceType']}/{resource['id']}"))

    for doc in documents:
        entries.append((_document_reference(case, doc), f"DocumentReference/{doc.doc_id}"))

    return entries


def transaction_bundle(entries: list[Entry]) -> Resource:
    """PUT-based transaction so reseeding is idempotent and IDs stay stable."""
    return {
        "resourceType": "Bundle",
        "type": "transaction",
        "entry": [
            {
                "fullUrl": f"urn:careauth:{url}",
                "resource": resource,
                "request": {"method": "PUT", "url": url},
            }
            for resource, url in entries
        ],
    }
