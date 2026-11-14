"""Render the measured Phase 1 JSON artifact; never infer live-model scores."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
data = json.loads((ROOT / "docs/benchmarks/phase-1-mock.json").read_text())
rules = data["rule_validation"]
rows = "\n".join(
    f"| {row['fixture']} | {row['status_before_post']} | "
    f"{', '.join(row['rule_codes']) or row['error_code'] or ('EXACT_FILE_RETURNED' if row['duplicate_file'] else 'none')} | "
    f"{row['post_http']} | {row['latency_ms']:.3f} |"
    for row in data["cases"]
)
text = f"""# Phase 1 fixture benchmark — mock workflow only

Measured at {data["generated_at"]} (UTC) on local Docker/PostgreSQL 16.
Dataset: `{data["dataset"]}`. **{data["case_count"]} submissions, {data["distinct_file_hashes"]} distinct file hashes.**
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
| Preventing a new ledger entry when required | 16 submissions | {data["tp"]} | {data["fp"]} | {data["fn"]} | {data["tn"]} | {data["precision"]:.0%} | {data["recall"]:.0%} |
| Rule validation only | {rules["case_count"]} extracted, non-exact-duplicate cases | {rules["tp"]} | {rules["fp"]} | {rules["fn"]} | {rules["tn"]} | {rules["tp"] / (rules["tp"] + rules["fp"]):.0%} | {rules["tp"] / (rules["tp"] + rules["fn"]):.0%} |

The first row includes one exact-file duplicate and one deliberate extraction
failure. The second excludes both: 9 known rule-blocking cases and 5 clean cases.
All 16 fixture contracts passed, including expected failure and duplicate behavior;
no case was discarded. A failed request aborts the benchmark with a nonzero exit
rather than silently contributing a successful observation. Failures in this run: 0.

## Latency (mock, not a service-level promise)

- p50: **{data["p50_ms"]:.3f} ms**; p95: **{data["p95_ms"]:.3f} ms**.
- Interval: {data["latency_scope"]}.
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
{rows}

Machine-readable artifacts: [JSON](benchmarks/phase-1-mock.json),
[CSV](benchmarks/phase-1-mock.csv). They include all sample hashes and outcomes.

## Reproduce

From the repository root with the private Compose PostgreSQL running:

```powershell
docker compose build backend
docker compose run --rm --no-deps -T -v ./docs/benchmarks:/results backend python -m app.qa benchmark --output /results/phase-1-mock.json
.\\.venv\\Scripts\\python.exe scripts/write_benchmark_report.py
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
"""
(ROOT / "docs/benchmark.md").write_text(text, encoding="utf-8")
