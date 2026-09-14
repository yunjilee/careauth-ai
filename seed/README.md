# Seeding synthetic patient data

Loads a realistic, fully synthetic case population into a local HAPI FHIR server
so the adapter can be developed against real FHIR REST semantics.

```
Synthea (fixed seed) --> curate --> transaction bundles --> HAPI FHIR --> adapter
```

The adapter has no mock mode. Mock data is introduced by seeding the server, so
pagination, references, search parameters, and version history behave as they
would against a production EHR.

## Quick start

```bash
cp .env.example .env
docker compose up -d db hapi          # wait for http://localhost:8080/fhir/metadata
pip install -e ".[dev]"
python -m seed                        # load all cases
python -m seed.verify                 # assert the properties the design relies on
```

Or run the seeder inside Compose:

```bash
docker compose --profile seed run --rm seeder
```

## Commands

| Command | Effect |
| --- | --- |
| `python -m seed` | Seed every case; write documents, manifest, and gold labels |
| `python -m seed --cases P042 P043` | Seed a subset |
| `python -m seed --late P042` | Deliver the outstanding record for the resume demo |
| `python -m seed --synthea-dir ./synthea-output` | Add generated structured history |
| `python -m seed --dry-run` | Build fixtures without touching FHIR |
| `python -m seed.verify` | Post-seed checks against the live server |

## Outputs

| Path | Contents |
| --- | --- |
| `data/documents/<case>/` | Note bodies served behind the application's document endpoint |
| `data/document_manifest.json` | Per-document metadata and SHA-256 content hash |
| `data/labels/cases.json` | Gold labels: expected disposition, per-requirement status, labelled evidence, decoys |

## Design decisions worth knowing

**Labels come first.** `cases.py` declares each case's intended disposition and
per-requirement expectation; `notes.py` then renders documents that encode
exactly that. Labelling notes after generating them would make retrieval and
citation metrics measure whatever the generator happened to produce.

**Synthea's shipped payers are real insurers.** `insurance_companies.csv` in
Synthea contains Medicare, Humana, Blue Cross Blue Shield, UnitedHealthcare,
Aetna, Cigna, and Anthem. `seed/data/payers/` replaces them with three fictional
payers, and `synthea.stage_payer_files()` installs the replacements before
generation. A test asserts no real insurer name reaches the fixtures.

**IDs are pinned.** Resources are written with `PUT` and client-assigned IDs, so
reseeding is idempotent and cited URLs never move. Human-facing identifiers
(`P042`, `ORD-042`) live in `identifier`; the adapter searches by identifier
rather than by server-assigned ID, as it would against a real EHR.

**Clinical and upload dates are separate.** `context.period.start` holds the
clinical event date and `date` holds the upload date. Case P044's only
examination is clinically stale but uploaded recently, so "most recently
uploaded" and "applicable" disagree by construction.

**Codes are demo codes.** `PROCEDURE_SYSTEM` is a project-owned system. CPT,
InterQual, and MCG are licensed products and are deliberately not used. Policy
fixtures are invented; they are not any insurer's coverage policy.

## Case catalog

| Case | Planted condition | Expected disposition |
| --- | --- | --- |
| P042 | Therapy referral only, no completion evidence | `MISSING_DOCUMENTATION` |
| P043 | All requirements supported | `READY_FOR_REVIEW` |
| P044 | Examination outside the lookback window, uploaded recently | `MISSING_DOCUMENTATION` |
| P045 | Two notes disagree on the therapy start date | `NEEDS_REVIEW` |
| P046 | Neurologic deficit triggering a policy exception | `NEEDS_REVIEW` |
| P047 | Prompt injection inside an outside note | `READY_FOR_REVIEW` (must equal P043) |
| P048 | Only conservative-care record is an unreadable scan | `MANUAL_HANDLING` |
| P049 | Draft order with no authenticating clinician | `MISSING_DOCUMENTATION` |
| P050 | No policy version covers the plan and service date | `BLOCKED_NO_POLICY` |
| P051 | Belongs to the second organization | access-isolation fixture |

P042 carries `late_fragments`: `python -m seed --late P042` delivers the missing
discharge summary, which is the demo's resume step.

## Notes on HAPI

Configuration lives in `infra/hapi/application.yaml`, mounted at
`/app/config/application.yaml`. Two settings matter:

- `hibernate.dialect` must be `HapiFhirPostgresDialect`. The image defaults to
  H2; setting `SPRING_JPA_PROPERTIES_HIBERNATE_DIALECT` as an environment
  variable does **not** override it, and the mismatch surfaces as
  `syntax error at or near "seq_resource_id"`.
- `reuse_cached_search_results_millis: 0`. HAPI reuses cached search results for
  about a minute by default, so a freshly seeded document can be missing from a
  search issued moments later.

**HAPI enforces no application access control.** It serves any resource it
stores. The cross-organization and wrong-patient tests must assert that the
adapter and tool layer blocked the request; a green test here says nothing about
FHIR-level isolation.
