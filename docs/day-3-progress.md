# Day 3: corrections, review, posting and export

Implemented in the independent repository on `feature/invoice-exception-desk`.
Existing source documents, fixture answer keys and sibling applications were preserved.
The running local database was upgraded from `0002_processing` to
`0003_review_ledger` without replacing its invoice IDs or files.

## Changed files and working features

- `backend/app/modules/approvals/`: strict revision-aware requests, extraction-field
  corrections, before/after audit diffs, explicit revalidation, authenticated
  approvals/rejections, immutable decision notes, payload hash binding, and supplier
  registration/policies with audit events.
- `backend/app/modules/ledger/`: posting service, ledger response schemas and stable
  snapshots, CSV quoting/encoding/formula defenses.
- `backend/app/modules/validation/service.py`: validation batches, current batch
  pointers, sorted business-key locks, shared supplier-policy row locks.
- Invoice routes/schemas: correction/revalidation/review/post endpoints, supplier
  creation, paginated ledger, CSV download, per-currency statistics, current batch,
  review history, validated revision and ledger ID in detail responses.
- DB models and `backend/alembic/versions/0003_review_ledger.py`: batch IDs,
  review hashes, ledger snapshots, data-preserving Day 2 backfill, and database
  UPDATE/DELETE guards for reviews and ledger rows.
- Processing audit metadata: validation run IDs; backend readiness/version updated
  to schema revision 0003 and application version 0.3.0.
- `backend/app/smoke.py`: repeatable full synthetic API demonstration, including
  correction/approval/posting, duplicate rejection, idempotency, audit and CSV.
- `backend/tests/test_review_posting.py`, `test_csv_export.py`, and the migration
  assertion in `test_postgres.py`: business, transaction, concurrency, authorization,
  history, snapshot and export tests.
- `README.md` and `docs/architecture.md`: current API, JSON request examples,
  retry/posting semantics, exact commands and remaining limits.

## Verified behavior

- Real corrections increment the revision, preserve extracted data, clear current
  validation, set sticky review requirements, and record field-level before/after
  changes. A no-change correction records an event without inventing a new revision.
- Corrected invoices require explicit current-revision revalidation, then current
  payload approval. Approvals never waive blockers and record the server-authenticated
  actor, revision and canonical payload SHA-256.
- Adding a supplier does not bypass validation or human review. Supplier thresholds
  require a currency; JPY thresholds must be integral.
- Posting rechecks blockers within the posting transaction. Row/advisory locks and
  independent DB uniqueness protect both same-invoice retries and business identity.
  Ledger insert, invoice transition and audit commit together; simulated audit failure
  rolls them all back. A forced uniqueness conflict returns HTTP 409 with no partial
  new ledger entry.
- Failed fresh checks persist current rule failures and review state before HTTP 409.
  A formerly ready invoice can therefore be blocked by a newly discovered duplicate
  or changed supplier policy. Rejected peers stop blocking their original; existing
  ledger identities remain duplicates.
- Concurrent posts return the same ledger ID; concurrent corrections allow one
  expected revision to succeed; concurrent identical approvals create one decision.
- Posted/rejected invoices reject edits and revalidation. Review and ledger records
  reject ordinary database UPDATE/DELETE. This is not protection from a DB owner
  deliberately removing constraints or triggers.
- Exports use posted snapshots, not mutable supplier display names. CSV includes
  only posted records, quotes commas/quotes/newlines, uses UTF-8 BOM, and prefixes
  potentially active formulas, including mixed Unicode whitespace/control prefixes.
  Dashboard totals remain separated by currency.

## Actually executed checks

| Command/check | Actual result |
| --- | --- |
| `docker compose build backend` | Linux image built successfully using existing pinned dependencies |
| `docker compose exec -T backend alembic upgrade head` | Applied `0002_processing -> 0003_review_ledger` on the existing database |
| Initial Linux/PostgreSQL suite | 136 passed; one existing Starlette HTTPX deprecation warning |
| Final Linux/PostgreSQL suite below | **137 passed**, no skips; one existing deprecation warning |
| `.venv/Scripts/python.exe scripts/dev.py test` | **84 passed**, 53 PostgreSQL tests explicitly skipped in this Windows non-DB run |
| Ruff lint and formatting | Passed; 54 Python files formatted |
| `pip check`, staged whitespace and local-credential checks | Passed; no broken dependencies or configured local credentials staged |
| `docker compose exec -T backend python -m app.smoke` twice | Both passed; same two ledger IDs, corrected revision 2, rejected duplicate, verified source download/audit, two CSV rows |
| `docker compose ps` | Backend and PostgreSQL healthy on localhost |

Final full test command:

```powershell
docker compose exec -T backend python -c "import os,pytest; os.environ['TEST_DATABASE_URL']=os.environ['DATABASE_URL']; raise SystemExit(pytest.main(['-q','-x','--tb=short','-p','no:cacheprovider']))"
```

The final extra regression test checks mixed Unicode whitespace plus BOM/zero-width
characters before a formula, beyond the existing plain-prefix and quoting tests.
The real SDK tests still use a fake HTTP transport; no live Gemini API call was made.

## Live demo state

The local demo has two synthetic `POSTED` invoices (1150.00 and corrected 2300.00
USD) and a rejected altered duplicate. The correction audit retains the original
2500.00 total and corrected 2300.00 total. Replaying the demo does not create more
ledger entries or silently modify terminal invoices. View the API at
`http://localhost:8000/docs`, using the generated local `.env` operator credentials.

Run `docker compose exec backend python -m app.smoke` to replay it, or use the JSON
examples in the README for fresh non-terminal invoices. `make demo` runs startup,
migration, seed and the same live demonstration on systems with GNU Make.

## Remaining scope

Day 4: Next.js dashboard with correction/review UI, n8n workflow JSON, integration
key ingress and optional Gmail/notification configuration. Day 5: broader QA,
fixture benchmark, deployment/read-only portfolio configuration and demo materials.

Current approvals are exposed through the authenticated API/OpenAPI interface;
the dashboard is not implemented yet. The ledger is internal PostgreSQL state;
there are no payments or ERP writebacks. Automatic posting is not implemented;
keep `AUTO_POST_CLEAN=false`. CSV generation is in memory for this small demo.
Legacy approvals without a bound payload hash cannot authorize posting.

The mock extractor is the running extraction mode. Live Gemini requires a key and
supported model; Gmail, Telegram and n8n are not connected. No public deployment
or paid provisioning was performed. GitHub publication remains deferred until
access is restored, as previously authorized.
