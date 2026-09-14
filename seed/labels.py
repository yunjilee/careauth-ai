"""Emit the gold label set alongside the seeded cases."""

from __future__ import annotations

import json
from pathlib import Path

from . import config
from .cases import CaseSpec, Fragment
from .notes import DocumentSpec


def build_label(case: CaseSpec, documents: list[DocumentSpec]) -> dict:
    evidence: dict[str, list[str]] = {req: [] for req in config.REQUIREMENTS}
    decoys: dict[str, list[str]] = {req: [] for req in config.REQUIREMENTS}

    for doc in documents:
        for req in doc.supports:
            evidence.setdefault(req, []).append(doc.doc_id)
        for req in doc.decoy_for:
            decoys.setdefault(req, []).append(doc.doc_id)

    if not case.has(Fragment.UNSIGNED_ORDER):
        evidence["REQ-ORDER"].append(case.order_id)

    return {
        "case_id": case.case_id,
        "order_id": case.order_id,
        "organization": case.org,
        "payer": config.PAYERS[case.payer]["name"],
        "plan": config.PAYERS[case.payer]["plans"][case.plan]["name"],
        "service_date": case.service_date.isoformat(),
        "expected_disposition": case.disposition.value,
        "expected_requirements": {k: v.value for k, v in case.expected.items()},
        "labeled_evidence": {k: sorted(v) for k, v in evidence.items() if v},
        "decoy_sources": {k: sorted(v) for k, v in decoys.items() if v},
        "planted_fragments": [f.value for f in case.fragments],
        "rationale": case.rationale,
    }


def write_labels(labels: list[dict]) -> Path:
    config.LABEL_DIR.mkdir(parents=True, exist_ok=True)
    path = config.LABEL_DIR / "cases.json"
    path.write_text(json.dumps(labels, indent=2, sort_keys=True), encoding="utf-8")
    return path
