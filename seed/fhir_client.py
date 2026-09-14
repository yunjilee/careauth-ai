"""Minimal FHIR REST client used only by the seeder."""

from __future__ import annotations

import time
from typing import Any

import httpx

FHIR_JSON = "application/fhir+json"


class FhirError(RuntimeError):
    pass


class FhirClient:
    def __init__(self, base_url: str, timeout: float = 60.0) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            timeout=timeout,
            headers={"Accept": FHIR_JSON, "Content-Type": FHIR_JSON},
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "FhirClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def wait_until_ready(self, timeout_seconds: int = 300, interval: float = 3.0) -> None:
        """Poll the capability statement until the server answers."""
        deadline = time.monotonic() + timeout_seconds
        last: Exception | None = None
        while time.monotonic() < deadline:
            try:
                response = self._client.get(f"{self.base_url}/metadata", timeout=10.0)
                if response.status_code == 200:
                    return
                last = FhirError(f"metadata returned {response.status_code}")
            except httpx.HTTPError as exc:  # server not up yet
                last = exc
            time.sleep(interval)
        raise FhirError(f"FHIR server not ready at {self.base_url}: {last}")

    def transaction(self, bundle: dict[str, Any]) -> dict[str, Any]:
        response = self._client.post(self.base_url, json=bundle)
        if response.status_code >= 400:
            raise FhirError(
                f"transaction failed ({response.status_code}): {response.text[:2000]}"
            )
        return response.json()

    def read(self, resource_type: str, resource_id: str) -> dict[str, Any] | None:
        response = self._client.get(f"{self.base_url}/{resource_type}/{resource_id}")
        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            raise FhirError(f"read failed ({response.status_code}): {response.text[:500]}")
        return response.json()

    def search(self, resource_type: str, **params: str) -> list[dict[str, Any]]:
        """Search, following `next` links so pagination is exercised."""
        url: str | None = f"{self.base_url}/{resource_type}"
        query: dict[str, str] | None = params
        results: list[dict[str, Any]] = []
        while url:
            response = self._client.get(url, params=query)
            if response.status_code >= 400:
                raise FhirError(
                    f"search failed ({response.status_code}): {response.text[:500]}"
                )
            bundle = response.json()
            results.extend(e["resource"] for e in bundle.get("entry", []) if "resource" in e)
            url = next(
                (l["url"] for l in bundle.get("link", []) if l.get("relation") == "next"),
                None,
            )
            query = None
        return results


def summarize_transaction(response: dict[str, Any]) -> tuple[int, list[str]]:
    """Return (success count, list of failure descriptions)."""
    failures: list[str] = []
    successes = 0
    for entry in response.get("entry", []):
        status = str(entry.get("response", {}).get("status", ""))
        if status[:1] in {"2"}:
            successes += 1
        else:
            failures.append(status or "unknown status")
    return successes, failures
