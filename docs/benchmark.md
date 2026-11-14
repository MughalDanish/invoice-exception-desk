# Phase 1 fixture benchmark — mock workflow only

Measured at 2026-11-14T07:13:49.181556+00:00 (UTC) on local Docker/PostgreSQL 16.
Dataset: `phase-1-original-16-v1`. **16 submissions, 15 distinct file hashes.**
Original PDFs and answer keys were not changed. No live AI, Gmail, Telegram or cloud
account was used. Phase 2 results are not included in this Phase 1 report.

## Protocol and denominators

`backend/app/qa.py::benchmark` creates a fresh random PostgreSQL schema per case,
migrates it to the real head, seeds approved synthetic vendors, and drives the real
FastAPI API with its mock extractor. For each duplicate case it first posts the
reference clean-001 invoice. Then it uploads the target, processes new documents,
reads persisted rules, attempts explicit posting, and counts ledger rows. Every
schema is dropped in a finally block. Existing application tables are untouched.

Labels are the original development fixture scenarios/expected codes. The same
answer key supplies the mock extractor, so this is a reproducible software contract
and rule test, **not a held-out model evaluation**. Expected codes are checked as
a subset because an invoice may correctly have multiple blockers. The exact-copy
case returns its existing posted invoice, not a new NEEDS_REVIEW record.

| Measurement | Denominator | TP | FP | FN | TN | Precision | Recall |
|---|---:|---:|---:|---:|---:|---:|---:|
| Preventing a new ledger entry when required | 16 submissions | 11 | 0 | 0 | 5 | 100% | 100% |
| Rule validation only | 14 extracted, non-exact-duplicate cases | 9 | 0 | 0 | 5 | 100% | 100% |

The first row includes one exact-file duplicate and one deliberate extraction
failure. The second excludes both: 9 known rule-blocking cases and 5 clean cases.
All 16 fixture contracts passed, including expected failure and duplicate behavior;
no case was discarded. A failed request aborts the benchmark with a nonzero exit
rather than silently contributing a successful observation. Failures in this run: 0.

## Latency (mock, not a service-level promise)

- p50: **160.523 ms**; p95: **842.362 ms**.
- Interval: upload + processing + detail + posting attempt + ledger read; excludes schema setup/reference seeding.
- Nearest-rank percentile over 16 observations; p95 is the maximum. Cold parser
  caches, host load and local storage affect results. No load/concurrency benchmark
  or network/browser timing is implied.
- Live Gemini latency, field accuracy, tokens and cost: **NOT RUN**. No model calls
  or paid provider calls occurred. Scripted mock answer replay is not AI accuracy.

## Per-fixture observed result

POST means the explicit posting attempt; 200 on an exact repeat returns the same
ledger ID without adding a row. 409 is a business refusal, not a transport failure.

| Fixture | State before post | Failed codes / extraction outcome | POST HTTP | Mock ms |
|---|---|---|---:|---:|
| clean-001.pdf | READY_TO_POST | none | 200 | 842.362 |
| clean-002.pdf | READY_TO_POST | none | 200 | 602.410 |
| clean-003.pdf | READY_TO_POST | none | 200 | 652.136 |
| clean-004.pdf | READY_TO_POST | none | 200 | 181.135 |
| clean-005.pdf | READY_TO_POST | none | 200 | 155.367 |
| wrong-total.pdf | NEEDS_REVIEW | TOTAL_MISMATCH | 409 | 194.702 |
| wrong-line.pdf | NEEDS_REVIEW | LINE_TOTAL_MISMATCH | 409 | 192.395 |
| wrong-tax.pdf | NEEDS_REVIEW | TAX_RATE_MISMATCH | 409 | 160.523 |
| duplicate-copy.pdf | POSTED | EXACT_FILE_RETURNED | 200 | 79.939 |
| duplicate-resend.pdf | NEEDS_REVIEW | DUPLICATE_INVOICE | 409 | 154.454 |
| duplicate-altered.pdf | NEEDS_REVIEW | DUPLICATE_INVOICE | 409 | 254.630 |
| unknown-vendor-1.pdf | NEEDS_REVIEW | UNAPPROVED_VENDOR | 409 | 148.449 |
| unknown-vendor-2.pdf | NEEDS_REVIEW | UNAPPROVED_VENDOR | 409 | 138.372 |
| missing-invoice_number.pdf | NEEDS_REVIEW | MISSING_REQUIRED_FIELD | 409 | 209.990 |
| missing-invoice_date.pdf | NEEDS_REVIEW | MISSING_REQUIRED_FIELD | 409 | 146.352 |
| extraction-failure.pdf | EXTRACTION_FAILED | MOCK_EXTRACTION_FAILED | 409 | 110.932 |

Machine-readable artifacts: [JSON](benchmarks/phase-1-mock.json),
[CSV](benchmarks/phase-1-mock.csv). They include all sample hashes and outcomes.

## Reproduce

From the repository root with the private Compose PostgreSQL running:

```powershell
docker compose build backend
docker compose run --rm --no-deps -T -v ./docs/benchmarks:/results backend python -m app.qa benchmark --output /results/phase-1-mock.json
.\.venv\Scripts\python.exe scripts/write_benchmark_report.py
```

Latency values and generation time naturally change on rerun. Compare case outcomes
and denominators, not byte identity of timing reports. The isolated-schema DB role
must be able to create/drop schemas. The public export is generated separately.

## Coverage limits

This development corpus has five clean digital PDFs, three arithmetic cases, three
duplicate submissions, two unapproved suppliers, two missing fields and one extraction
failure. It contains no noisy scanned hold-out set, no independent human-labeled
field ground truth, no true PO/receipt/email corpus and no production data. Unit tests
exercise additional date, currency, precision, outlier and uncertainty boundaries,
but those are not added to this 16-case benchmark's denominator. Do not claim 98%
live extraction or 100-case Phase 2 evaluation from these results.
