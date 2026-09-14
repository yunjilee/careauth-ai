from datetime import timedelta

import pytest

from seed import config, curate, labels, notes
from seed.cases import CATALOG, Disposition, Fragment, Status


def _docs(case):
    return notes.build_documents(case)


@pytest.mark.parametrize("case", CATALOG, ids=lambda c: c.case_id)
def test_every_case_produces_a_valid_bundle(case):
    bundle = curate.transaction_bundle(curate.build_case_entries(case, _docs(case)))
    assert bundle["type"] == "transaction"
    assert all(e["request"]["method"] == "PUT" for e in bundle["entry"])
    urls = [e["request"]["url"] for e in bundle["entry"]]
    assert len(urls) == len(set(urls)), "duplicate resource ids in one transaction"


@pytest.mark.parametrize("case", CATALOG, ids=lambda c: c.case_id)
def test_business_identifiers_are_pinned(case):
    entries = dict(
        (url, resource) for resource, url in curate.build_case_entries(case, _docs(case))
    )
    patient = entries[f"Patient/{case.case_id}"]
    assert patient["identifier"][0]["value"] == case.case_id
    order = entries[f"ServiceRequest/{case.order_id}"]
    assert order["identifier"][0]["value"] == case.order_id
    assert order["code"]["coding"][0]["code"] == config.DEMO_PROCEDURE_CODE


@pytest.mark.parametrize("case", CATALOG, ids=lambda c: c.case_id)
def test_order_signature_matches_label(case):
    order = next(
        r for r, url in curate.build_case_entries(case, _docs(case))
        if url.startswith("ServiceRequest/")
    )
    signed = "requester" in order
    order_is_missing = case.expected["REQ-ORDER"] is Status.MISSING
    assert signed is not order_is_missing


def test_unsigned_order_is_draft():
    case = next(c for c in CATALOG if c.has(Fragment.UNSIGNED_ORDER))
    order = next(
        r for r, url in curate.build_case_entries(case, _docs(case))
        if url.startswith("ServiceRequest/")
    )
    assert order["status"] == "draft"
    assert "requester" not in order


def test_stale_exam_is_uploaded_after_a_recent_document():
    """Upload recency must not imply clinical applicability."""
    case = next(c for c in CATALOG if c.has(Fragment.EXAM_STALE))
    stale = next(d for d in _docs(case) if d.type_code == notes.EXAM_NOTE)
    age_days = (case.service_date - stale.clinical_date).days
    assert age_days > config.EXAM_LOOKBACK_DAYS
    assert stale.upload_date > stale.clinical_date
    assert (case.service_date - stale.upload_date).days < config.EXAM_LOOKBACK_DAYS


def test_completed_course_meets_the_duration_rule():
    case = next(c for c in CATALOG if c.has(Fragment.CONSERVATIVE_COMPLETE))
    doc = next(d for d in _docs(case) if "REQ-CONSERVATIVE" in d.supports)
    assert "course completed" in doc.body.lower()


def test_referral_only_case_has_no_supporting_evidence():
    case = next(c for c in CATALOG if c.has(Fragment.CONSERVATIVE_REFERRAL_ONLY))
    docs = _docs(case)
    assert not any("REQ-CONSERVATIVE" in d.supports for d in docs)
    assert any("REQ-CONSERVATIVE" in d.decoy_for for d in docs)
    assert case.expected["REQ-CONSERVATIVE"] is Status.MISSING


def test_injection_case_matches_its_clean_twin():
    """The injected note must not change the expected outcome."""
    injected = next(c for c in CATALOG if c.has(Fragment.PROMPT_INJECTION))
    clean = next(
        c for c in CATALOG
        if c.disposition is Disposition.READY_FOR_REVIEW
        and not c.has(Fragment.PROMPT_INJECTION)
        and c.org == injected.org
    )
    assert injected.expected == clean.expected
    body = next(d.body for d in _docs(injected) if "cover" in d.doc_id)
    assert "ignore all previous instructions" in body.lower()


def test_unreadable_source_is_not_labelled_missing():
    case = next(c for c in CATALOG if c.has(Fragment.UNREADABLE_SCAN))
    assert case.expected["REQ-CONSERVATIVE"] is not Status.MISSING
    assert case.disposition is Disposition.MANUAL_HANDLING


def test_cross_organization_fixture_exists():
    orgs = {c.org for c in CATALOG}
    assert len(orgs) > 1, "access isolation needs a second organization"


def test_no_real_insurer_names_in_fixtures():
    real = {"medicare", "medicaid", "humana", "blue cross", "aetna", "cigna",
            "anthem", "unitedhealthcare", "kaiser"}
    names = " ".join(p["name"] for p in config.PAYERS.values()).lower()
    assert not any(name in names for name in real)


@pytest.mark.parametrize("case", CATALOG, ids=lambda c: c.case_id)
def test_labels_cover_every_requirement(case):
    label = labels.build_label(case, _docs(case))
    assert set(label["expected_requirements"]) == set(config.REQUIREMENTS)
    assert label["expected_disposition"] == case.disposition.value


def test_late_delivery_changes_the_outcome_inputs():
    case = next(c for c in CATALOG if c.late_fragments)
    before = _docs(case)
    after = notes.build_documents(case, case.fragments + case.late_fragments)
    assert len(after) > len(before)
    assert any("REQ-CONSERVATIVE" in d.supports for d in after)
    assert not any("REQ-CONSERVATIVE" in d.supports for d in before)


def test_document_dates_are_never_after_the_service_date():
    for case in CATALOG:
        for doc in _docs(case):
            assert doc.clinical_date <= case.service_date + timedelta(days=1)
