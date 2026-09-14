"""Synthea integration.

Two responsibilities:

1. Stage the fictional payer files so generation never emits a real insurer name.
   Synthea ships Medicare, Humana, Blue Cross Blue Shield, UnitedHealthcare,
   Aetna, Cigna, and Anthem in ``insurance_companies.csv``.
2. Import generated structured history onto curated patients.

Synthea is optional. Without it the seeder still produces a complete, coherent
fixture set; with it, each case gains a realistic longitudinal history.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from . import config
from .cases import CaseSpec

PAYER_FILES = ("insurance_companies.csv", "insurance_plans.csv")

# Types safe to import: each is valid with only `subject` as a reference.
IMPORTABLE = ("Condition", "Procedure", "MedicationRequest", "AllergyIntolerance")

REFERENCE_KEYS = {
    "encounter",
    "requester",
    "performer",
    "recorder",
    "asserter",
    "location",
    "partOf",
    "basedOn",
    "reasonReference",
    "supportingInformation",
    "context",
    "insurance",
    "informationSource",
}


def stage_payer_files(synthea_home: Path) -> list[Path]:
    """Copy the fictional payer CSVs over Synthea's shipped files."""
    target = synthea_home / "src" / "main" / "resources" / "payers"
    if not target.is_dir():
        raise FileNotFoundError(f"not a Synthea checkout: {synthea_home}")
    source = Path(__file__).parent / "data" / "payers"
    written = []
    for name in PAYER_FILES:
        backup = target / f"{name}.original"
        if not backup.exists():
            shutil.copy2(target / name, backup)
        shutil.copy2(source / name, target / name)
        written.append(target / name)
    return written


def generate(synthea_home: Path, output_dir: Path, population: int = 20) -> None:
    """Run Synthea with a pinned seed. Requires a Synthea checkout with Java."""
    stage_payer_files(synthea_home)
    output_dir.mkdir(parents=True, exist_ok=True)
    script = "run_synthea.bat" if (synthea_home / "run_synthea.bat").exists() else "./run_synthea"
    subprocess.run(
        [
            script,
            "-p", str(population),
            "-s", str(config.SYNTHEA_SEED),
            "-cs", str(config.SYNTHEA_SEED),
            "--exporter.baseDirectory", str(output_dir),
            "--exporter.fhir.export", "true",
            "--exporter.hospital.fhir.export", "false",
            "--exporter.practitioner.fhir.export", "false",
            "--exporter.years_of_history", "5",
        ],
        cwd=synthea_home,
        check=True,
    )


def _patient_bundles(synthea_dir: Path) -> list[Path]:
    fhir_dir = synthea_dir / "fhir" if (synthea_dir / "fhir").is_dir() else synthea_dir
    skip = ("hospitalInformation", "practitionerInformation")
    # Sorted for determinism: case N always draws the same generated history.
    return sorted(
        p for p in fhir_dir.glob("*.json") if not p.name.startswith(skip)
    )


def _strip_references(resource: dict[str, Any]) -> dict[str, Any]:
    """Remove references to resources this seeder does not import.

    HAPI enforces referential integrity on write, so a dangling reference fails
    the whole transaction.
    """
    cleaned = {k: v for k, v in resource.items() if k not in REFERENCE_KEYS}
    cleaned.pop("contained", None)
    return cleaned


def load_history(synthea_dir: Path, case: CaseSpec, index: int) -> list[dict[str, Any]]:
    """Import one generated patient's structured history onto a curated case."""
    bundles = _patient_bundles(synthea_dir)
    if not bundles:
        return []

    bundle = json.loads(bundles[index % len(bundles)].read_text(encoding="utf-8"))
    imported: list[dict[str, Any]] = []
    counter = 0

    for entry in bundle.get("entry", []):
        resource = entry.get("resource") or {}
        if resource.get("resourceType") not in IMPORTABLE:
            continue
        counter += 1
        cleaned = _strip_references(resource)
        cleaned["id"] = f"syn-{case.case_id}-{counter}"
        cleaned["subject"] = {"reference": f"Patient/{case.case_id}"}
        cleaned.pop("identifier", None)
        imported.append(cleaned)

    return imported
