"""Seeder entrypoint.

    python -m seed --wait 300
    python -m seed --cases P042 P043 --synthea-dir ./synthea-output
    python -m seed --late P042          # deliver the outstanding record
    python -m seed --dry-run            # write fixtures, skip the FHIR server
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import config, curate, documents, labels, notes, synthea
from .cases import CaseSpec, select
from .fhir_client import FhirClient, FhirError, summarize_transaction


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="seed", description=__doc__)
    parser.add_argument("--fhir-base", default=config.FHIR_BASE_URL)
    parser.add_argument("--cases", nargs="*", default=None, help="case ids; default all")
    parser.add_argument("--wait", type=int, default=180, help="seconds to wait for HAPI")
    parser.add_argument(
        "--synthea-dir",
        type=Path,
        default=None,
        help="Synthea FHIR output directory to draw structured history from",
    )
    parser.add_argument(
        "--late",
        nargs="*",
        default=None,
        metavar="CASE_ID",
        help="deliver each case's late-arriving documents (demo resume step)",
    )
    parser.add_argument("--dry-run", action="store_true", help="skip all FHIR writes")
    return parser


def _fragments_for(case: CaseSpec, late_ids: set[str]) -> tuple:
    if case.case_id in late_ids:
        return case.fragments + case.late_fragments
    return case.fragments


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    late_ids = set(args.late or [])
    cases = select(tuple(args.cases) if args.cases else None)

    if late_ids - {c.case_id for c in cases}:
        print(f"late case ids not in selection: {sorted(late_ids)}", file=sys.stderr)
        return 2

    client: FhirClient | None = None
    if not args.dry_run:
        client = FhirClient(args.fhir_base)
        print(f"waiting for FHIR server at {args.fhir_base} ...")
        client.wait_until_ready(timeout_seconds=args.wait)
        print("server ready")

    try:
        if client:
            infra = curate.build_infrastructure()
            response = client.transaction(curate.transaction_bundle(infra))
            ok, failures = summarize_transaction(response)
            print(f"infrastructure: {ok} resources loaded")
            if failures:
                print(f"  failures: {failures}", file=sys.stderr)
                return 1

        manifest_rows: list[dict] = []
        label_rows: list[dict] = []

        for index, case in enumerate(cases):
            fragments = _fragments_for(case, late_ids)
            docs = notes.build_documents(case, fragments)

            manifest_rows.extend(documents.write_documents(case, docs))
            label_rows.append(labels.build_label(case, docs))

            history = []
            if args.synthea_dir:
                history = synthea.load_history(args.synthea_dir, case, index)

            entries = curate.build_case_entries(case, docs, history)

            if client:
                response = client.transaction(curate.transaction_bundle(entries))
                ok, failures = summarize_transaction(response)
                if failures:
                    print(f"{case.case_id}: FAILED {failures}", file=sys.stderr)
                    return 1
                suffix = " (+late records)" if case.case_id in late_ids else ""
                print(
                    f"{case.case_id}: {ok} resources, {len(docs)} documents, "
                    f"{len(history)} generated history resources "
                    f"-> {case.disposition.value}{suffix}"
                )
            else:
                print(f"{case.case_id}: {len(entries)} resources prepared (dry run)")

        manifest_path = documents.write_manifest(manifest_rows)
        label_path = labels.write_labels(label_rows)
        print(f"documents  -> {config.DOCUMENT_DIR}")
        print(f"manifest   -> {manifest_path}")
        print(f"gold labels-> {label_path}")

    except FhirError as exc:
        print(f"seed failed: {exc}", file=sys.stderr)
        return 1
    finally:
        if client:
            client.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
