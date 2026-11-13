# Day 2: extraction, validation, and recovery

Implemented in the isolated `invoice-exception-desk` repository on
`feature/invoice-exception-desk`. Day 1 application data and file paths were
preserved by the additive migration. No sibling application was modified.

## Files and working features

- `backend/app/modules/extraction/`: extractor protocol, hash-based fixture adapter,
  official Gemini SDK adapter, fixed provider schema, strict local Pydantic schema,
  processing orchestration, and sanitized error codes.
- `backend/app/modules/validation/`: pure Decimal rules plus transactional supplier,
  active-invoice and ledger duplicate queries, normalized fingerprint locking,
  and persisted validation results.
- `backend/app/modules/invoices/states.py`: explicit transition checks and audits.
- `backend/app/db/models.py` and `alembic/versions/0002_processing.py`: normalized
  business identity, sticky human-review flag, processing attempts and history.
- Invoice routes/schemas: authenticated processing/retry endpoint, attempt history
  in detail responses, human-review flag, and extracted supplier/number search.
- Backend configuration, Compose and `.env.example`: optional Gemini key/model,
  bounded HTTP timeout/retry settings, and USD tolerance.
- `backend/app/main.py`: version 0.2.0 and migration-aware readiness.
- `backend/app/smoke.py`: repeatable live API clean / wrong-total / altered-duplicate
  demonstration, original download integrity, auth and ingestion idempotency.
- `backend/tests/`: rule boundaries, strict numeric types, SDK HTTP contract,
  sanitized bounded retries, processing states, database migration, concurrency,
  and stale-worker recovery. Tests explicitly force mock extraction and blank
  live credentials; the SDK tests use a fake HTTP transport.
- Pinned dependency files: official `google-genai==1.75.0` and its dependencies.
- `README.md` and `docs/architecture.md`: current commands, configuration,
  state/retry behavior, supported currencies, and scope limits.

Processing commits `EXTRACTING` before external I/O, releases its DB transaction,
and atomically stores validated data, rules, attempts, audits and final state on
completion. Repeated requests do not overwrite successful extraction or corrected
data. Concurrent calls return the current attempt. Failed extraction requires
`retry=true`; interrupted attempts can be reclaimed after two minutes. A late old
worker receives HTTP 409 and cannot overwrite the new attempt's result.

The rule engine blocks missing/incomplete arithmetic, invalid dates, incorrect
line/subtotal/total/tax calculations, unknown/unapproved suppliers, business
duplicates (even with changed total), wrong/unsupported currencies, invalid monetary
precision/range, negative values, amount outliers, and uncertain/evidence-poor output.
No AI confidence score is treated as an approval signal.

## Actual verification

| Command/check | Result |
| --- | --- |
| Real SDK request construction via `httpx.MockTransport` | Passed: inline document MIME, structured schema, configured timeout, retry ceiling, and redacted logging |
| `.venv/Scripts/python.exe scripts/dev.py test --postgres` | **103 passed**, one Starlette HTTPX deprecation warning |
| `docker compose build backend` | Linux image built with pinned SDK and dependencies |
| `docker compose exec -T backend alembic upgrade head` | Applied `0001_foundation -> 0002_processing` to the existing PostgreSQL database |
| Initial full Linux/PostgreSQL run | **103 passed**, one Starlette HTTPX deprecation warning |
| `docker compose exec -T backend python -m app.smoke` | Live clean invoice ready; wrong total held with `TOTAL_MISMATCH`; altered duplicate held with `DUPLICATE_INVOICE`; auth, original bytes and ingestion dedupe passed |
| Ruff lint / format | Passed; 44 Python files formatted |
| `pip check` | No broken requirements |

Final regression check, including the additional simultaneous-business-duplicate
test: **104 passed**, one existing Starlette HTTPX deprecation warning, no skips.
Executed with:

```powershell
docker compose exec -T backend python -c "import os,pytest; os.environ['TEST_DATABASE_URL']=os.environ['DATABASE_URL']; raise SystemExit(pytest.main(['-q','-x','--tb=short','-p','no:cacheprovider']))"
```

The new race test uses two different source documents with the same business
identity, synchronizes their extraction completion, and verifies exactly one
`READY_TO_POST` and one `NEEDS_REVIEW` with a duplicate blocker. The earlier
103-test Windows run predates this one added test; the final 104-test run was
executed in the Linux container against PostgreSQL.

The final running image was rebuilt, both services were healthy, and the live
smoke demonstration passed again. All staged changes passed the whitespace and
local-credential checks. No Gemini key/model is configured in local `.env`.

Two implementation issues were found and fixed during development:

1. Pydantic's decimal digit limit includes the configured fractional places.
   The schema now permits the necessary integer range, while a deterministic
   rule rejects amounts that cannot fit the ledger. High-magnitude multiplication
   is performed in a local 64-digit Decimal context and tested without overflow.
2. The SDK rejected arbitrary-map `additionalProperties` when transforming the
   authoritative extraction schema. A fixed provider schema now requests string
   numbers and fixed evidence fields, followed by strict independent validation.
   This is verified against the actual SDK serialization path, not a fake client.

## What is mocked and what remains

The running demo uses `AI_MODE=mock` and synthetic fixtures. Gemini request/error
behavior was tested offline; **no live Gemini extraction or model accuracy benchmark
was run**. Live mode requires `GEMINI_API_KEY` and an account-supported
`GEMINI_MODEL`, followed by backend recreation; exact commands are in the README.

Only USD/EUR/GBP/JPY are currently supported. Mixed-rate taxes, discounts/shipping
allocation, credit notes, fuzzy vendor identity and calibrated extraction confidence
are outside this milestone. Source evidence is not proof of invoice authenticity.
Processing is synchronous with bounded SDK timeout/retry settings; there is no
automatic processing worker. Crash recovery uses explicit retry after lease expiry.

Day 2 stops at `READY_TO_POST`, `NEEDS_REVIEW`, or `EXTRACTION_FAILED`.
Approval, correction, revalidation API, rejection, ledger posting and CSV export
remain Day 3. Validation is a snapshot; Day 3 posting must recompute blockers in
its transaction. Nothing was approved or posted during the live demo.

Next milestone: revision-aware corrections and review, safe transactional posting,
fresh validation, ledger idempotency, audit diffs and sanitized CSV export.
Next.js and n8n remain Day 4. No Gemini/Gmail/Telegram credentials are connected,
and no public deployment was performed. GitHub publication remains deferred until
GitHub access is restored, as the owner previously authorized.
