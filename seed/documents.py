"""Write note bodies to the local document store and record content hashes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import config
from .cases import CaseSpec
from .notes import DocumentSpec

EXTENSIONS = {"text/plain": ".txt", "application/pdf": ".pdf.txt"}


def document_path(case: CaseSpec, doc: DocumentSpec) -> Path:
    suffix = EXTENSIONS.get(doc.content_type, ".txt")
    return config.DOCUMENT_DIR / case.case_id / f"{doc.doc_id}{suffix}"


def write_documents(case: CaseSpec, documents: list[DocumentSpec]) -> list[dict]:
    """Persist bodies and return manifest rows including content hashes.

    The content hash is what drives reprocessing: editing a fixture body changes
    the hash, which is the same signal a real changed document would produce.
    """
    manifest: list[dict] = []
    for doc in documents:
        path = document_path(case, doc)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = doc.body.encode("utf-8")
        path.write_bytes(payload)
        manifest.append(
            {
                "document_id": doc.doc_id,
                "case_id": case.case_id,
                "title": doc.title,
                "type": doc.type_code,
                "content_type": doc.content_type,
                "readable": doc.readable,
                "clinical_date": doc.clinical_date.isoformat(),
                "upload_date": doc.upload_date.isoformat(),
                "path": str(path.relative_to(config.DATA_DIR)),
                "content_hash": hashlib.sha256(payload).hexdigest(),
            }
        )
    return manifest


def write_manifest(rows: list[dict]) -> Path:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = config.DATA_DIR / "document_manifest.json"
    path.write_text(json.dumps(rows, indent=2, sort_keys=True), encoding="utf-8")
    return path
