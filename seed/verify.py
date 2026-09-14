"""Post-seed verification against a live HAPI server.

Run after `python -m seed`. Asserts the properties the design depends on rather
than merely that resources loaded.
"""

from __future__ import annotations

import sys

from seed import config
from seed.cases import CATALOG, CATALOG_BY_ID, Fragment
from seed.fhir_client import FhirClient

REAL_INSURERS = ("medicare", "medicaid", "humana", "blue cross", "aetna",
                 "cigna", "anthem", "unitedhealthcare", "kaiser")


def check(label: str, condition: bool, detail: str = "") -> bool:
    print(f"  [{'ok' if condition else 'FAIL'}] {label}{(' - ' + detail) if detail else ''}")
    return condition


def main(base: str) -> int:
    failures = 0
    with FhirClient(base) as fhir:
        fhir.wait_until_ready(60)

        print("business identifier search")
        found = fhir.search("ServiceRequest", identifier="ORD-042")
        failures += not check("ORD-042 resolves by identifier", len(found) == 1)
        if found:
            order = found[0]
            failures += not check(
                "demo procedure code preserved",
                order["code"]["coding"][0]["code"] == config.DEMO_PROCEDURE_CODE,
            )
            failures += not check("intended service date present",
                                  "occurrenceDateTime" in order)

        print("payer fixtures contain no real insurer")
        orgs = fhir.search("Organization", type="ins")
        names = " ".join(o.get("name", "") for o in orgs).lower()
        failures += not check("fictional payers only", not any(n in names for n in REAL_INSURERS), names)

        print("coverage carries payer and plan")
        covs = fhir.search("Coverage", beneficiary="Patient/P042")
        failures += not check("P042 coverage found", len(covs) == 1)
        if covs:
            klass = covs[0].get("class", [])
            failures += not check("plan recorded in Coverage.class",
                                  bool(klass) and "value" in klass[0],
                                  klass[0].get("name", "") if klass else "")

        print("clinical date and upload date are distinct")
        case = CATALOG_BY_ID["P044"]
        docs = fhir.search("DocumentReference", patient=case.case_id)
        stale = [d for d in docs if d["id"].endswith("exam-old")]
        failures += not check("stale exam present", len(stale) == 1)
        if stale:
            clinical = stale[0]["context"]["period"]["start"][:10]
            uploaded = stale[0]["date"][:10]
            failures += not check("uploaded later than the clinical event",
                                  uploaded > clinical, f"clinical={clinical} uploaded={uploaded}")

        print("unsigned order is not an active order")
        draft = fhir.search("ServiceRequest", identifier="ORD-049")
        failures += not check("draft status retained",
                              bool(draft) and draft[0]["status"] == "draft")
        failures += not check("no requester on unsigned order",
                              bool(draft) and "requester" not in draft[0])

        print("cross-organization fixture is separable")
        summit = config.ORGANIZATIONS["summit"]["id"]
        others = fhir.search("Patient", organization=f"Organization/{summit}")
        failures += not check("second organization has its own patients", len(others) >= 1,
                              ", ".join(p["id"] for p in others))

        print("version history exists for reseeded documents")
        doc_id = f"N-042-exam"
        doc = fhir.read("DocumentReference", doc_id)
        failures += not check("meta.versionId present",
                              bool(doc) and "versionId" in doc.get("meta", {}),
                              doc.get("meta", {}).get("versionId", "") if doc else "")

        print("every case is retrievable")
        for spec in CATALOG:
            patient = fhir.read("Patient", spec.case_id)
            failures += not check(f"{spec.case_id} present", patient is not None)

    print()
    print("PASS" if failures == 0 else f"{failures} CHECK(S) FAILED")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else config.FHIR_BASE_URL))
