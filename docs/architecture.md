# Architecture and Day 1 decisions

FastAPI is a modular monolith. PostgreSQL owns application state. Private files
are stored under UUID names on a dedicated local directory/volume. The dashboard
and integrations will call the API; no integration will own business rules.

```mermaid
flowchart LR
  Operator -->|HTTP Basic + upload| API[FastAPI]
  API --> PG[(PostgreSQL 16)]
  API --> Files[Private invoice volume]
  Seed[Synthetic fixture CLI] --> PG
  Seed --> Files
```

Day 1 implements ingestion and read APIs only. There is no extraction, approval,
or posting path yet. All accepted invoices stay `RECEIVED`, with revision 1.
Validation, review and ledger tables establish the schema for later milestones;
their presence does not imply those features work.

- Follow `PROJECT_SPEC.md` for the exact statuses and single demo operator.
  Users and line items do not need separate tables in this MVP: the local
  operator comes from environment variables, and line items belong to versioned
  JSON payloads. This resolves the broader examples in the supplied pasted brief.
  That brief is preserved in `IMPLEMENTATION_BRIEF.md`; its final instruction
  limits the current implementation to Day 1 and requires a results report before Day 2.
- SHA-256 is globally unique: uploading the same bytes from another source returns
  the existing invoice. A PostgreSQL transaction advisory lock serializes equal
  hashes; a unique constraint provides an independent database guard. Duplicate
  attempts append audit events. Business duplicates with different bytes are a
  separate Day 2 validation rule.
- Uploaded filename is display metadata only. Storage uses UUIDs, validates the
  path is under the configured root, and exposes files through an authenticated
  attachment response. No static upload directory is mounted publicly.
- Validate extension, declared MIME, actual signature, and parser acceptance.
  Reject encrypted PDFs, more than 100 PDF pages, and images over 25 megapixels.
  These are bounded demo limits, not a malware scanner. No remote URL ingestion.
- Reject files over 8 MiB. The ASGI middleware additionally caps the entire body
  at 8 MiB plus 64 KiB of multipart overhead, including chunked requests.
- File write and database insert are coordinated: normal transaction failures
  remove the newly written file. A process or host crash can leave an orphaned
  file; crash reconciliation is not implemented in Day 1. PostgreSQL is authoritative.
- Audits are append-only in API code and protected against UPDATE/DELETE by a
  database trigger. Database owners can still remove tables or triggers; this is
  not a claim of tamper-proof financial compliance.
- Startup refuses empty/default operator passwords; OpenAPI docs require auth.
  CORS permits the configured localhost frontend only. Basic auth is local-only;
  this milestone does not implement public portfolio mode.
- Initial migration is explicit and independent of mutable ORM metadata. Tests
  compare the migrated schema to the ORM and use isolated random schemas.

Official implementation references:

- [FastAPI file uploads](https://fastapi.tiangolo.com/tutorial/request-files/)
- [FastAPI HTTP Basic](https://fastapi.tiangolo.com/advanced/security/http-basic-auth/)
- [SQLAlchemy 2 PostgreSQL dialect](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html)

## Day 2: extraction and validation

The `Extractor` protocol has deterministic mock and optional Gemini implementations.
The mock matches source bytes by hash against the answer key. The Gemini adapter
uses the official SDK with an explicit fixed-object provider schema: the SDK rejects
arbitrary-map `additionalProperties` in its legacy response-schema path. All numeric
provider fields are strings. A separate strict Pydantic model validates the response
again, rejects unknown actions, floats, non-finite money, and oversized values.
The real SDK request transformation is exercised with an offline HTTP transport;
this is not a live-model accuracy test.

Processing claims an invoice under a row lock and commits `EXTRACTING` plus a
RUNNING attempt. It then releases the transaction for document/model I/O. Another
request observes the running attempt. Completion locks the invoice again and
refreshes cached ORM objects before checking ownership, preventing an expired worker
from overwriting a newer attempt. Explicit retries reclaim an interrupted attempt
after a two-minute lease. No periodic worker or automatic crash recovery exists yet.

Validation completion locks a normalized supplier/invoice fingerprint with a
transaction advisory lock, checks supplier policies and duplicates, records rules,
and stores parsed data with the resulting state in the same transaction. Exact
file deduplication remains enforced independently at ingestion. The migration adds
normalized identity columns, sticky human-review state, and processing-attempt history
without changing existing invoice IDs or file paths. The health endpoint requires
the current migration revision.

Day 2 stops at READY_TO_POST / NEEDS_REVIEW / EXTRACTION_FAILED. Day 3 will implement
corrections, revision-aware review, and transactional posting with fresh validation;
stored rule results alone must never authorize posting. The currency and arithmetic
limits, retry behavior, and live Gemini configuration are documented in the README.

- [Official Google Gen AI SDK](https://github.com/googleapis/python-genai)
