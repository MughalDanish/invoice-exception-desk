# Day 9 — scoped hybrid retrieval and evidence links

Implemented 18 November 2026. This is additive evidence functionality; original extraction, validation, approvals, posting and n8n behavior are unchanged.

## Working behavior

`evidence/search.py` runs two real PostgreSQL retrieval paths. Exact SQL looks for the invoice's server-normalized identifier inside supporting text. Full-text search uses PostgreSQL 16 English tokenization, stemming and cover-density ranking over a bounded server-generated vocabulary. A materialized CTE filters **both invoice UUID and normalized supplier** and selects the latest version of each source before relevance ranking. No caller can supply SQL or an alternative supplier scope through the API.

Reciprocal rank fusion combines the two rankings using `1 / (60 + rank)`. Python `Fraction` avoids floating-point tie ambiguity; citation ID breaks equal-score ties deterministically. Each path returns at most twelve sources, reads one extra row to detect truncation, and fusion also returns at most twelve. Missing supplier identity returns no evidence.

Strict frozen citation contracts contain source UUID, exact version, invoice/supplier scope, source kind, canonical text hash, exact excerpt and character location. Documents are already limited to 1,000 characters, so the complete bounded text is retained and its hash can be verified. No generated summary substitutes for source text. `validate_citation` rejects references absent from the captured fused results.

The authenticated GET `/api/v1/invoices/{invoice_id}/evidence/{source_id}/versions/{version}` resolves the cited historical version after deriving supplier scope from the current invoice. It returns `Cache-Control: no-store`. New source versions affect new captures; old citations can still resolve to their immutable historical source. The parent integration adds this retrieval snapshot to investigation freshness checks and registers the private router.

## Files

- `backend/app/modules/evidence/{__init__,schemas,search,routes}.py`: strict provenance, SQL/FTS retrieval, deterministic fusion, citation membership and private resolution.
- `backend/alembic/versions/0008_evidence_search.py`: additive GIN expression index; downgrade removes only this index.
- `backend/tests/test_evidence_retrieval.py`: merge, forged hash/scope, real SQL/FTS, source versions, missing identity, injection-shaped query text, truncation and source authorization tests.
- `fixtures/investigation/retrieval-cases.json`: separately versioned annotated synthetic development corpus.
- `scripts/run_retrieval_evaluation.py`: actual PostgreSQL SQL/FTS/RRF comparison in disposable schemas.
- `docs/learning-day-9.md`: owner learning walkthrough and exercise.

## Actual evaluation

Command: `.venv/Scripts/python.exe scripts/run_retrieval_evaluation.py` — **exit 0**. Three synthetic development scenarios contain nine source documents, six annotated relevant. Every temporary schema was removed. Output: ignored `storage/day-9-retrieval-evaluation.json`.

| Retrieval | Relevant retrieved / relevant | Macro recall@5 |
|---|---:|---:|
| Exact SQL | 3 / 6 | 0.50 |
| PostgreSQL FTS | 6 / 6 | 1.00 |
| SQL + FTS RRF | 6 / 6 | 1.00 |

Each scenario contains only three sources: this demonstrates lexical coverage beyond identity matching, **not a demanding top-five ranking benchmark**. FTS and RRF tie here; no improvement from fusion over FTS is claimed. A larger frozen held-out evaluation remains Day 15 work. No live model calls, model accuracy or semantic retrieval quality were measured.

`pg_available_extensions` returned no `vector` extension. Optional pgvector and embeddings were therefore not installed or simulated. PostgreSQL FTS is lexical retrieval, not vector semantic retrieval.

Focused regression first run: **3 passed, 2 failed**. One test compared a UUID to an API string; its assertion was corrected. The second ran before the parent had registered the evidence router and received 404. Repeat with `pytest tests/test_evidence_retrieval.py -k 'not historical_source' -q --tb=short -p no:cacheprovider` and privately configured `TEST_DATABASE_URL`: **4 passed, 1 deselected, exit 0, 4.24 seconds**. After private router registration, all five focused tests passed: **5 passed, 13 existing per-request-cookie deprecation warnings, exit 0, 36.41 seconds**. Historical version resolution, unauthenticated rejection, missing version and wrong-supplier denial all passed. After durable service integration, added an independent freshness check that disables the older document-inventory gate and proves a new source version alone invalidates the retrieval snapshot without financial mutation. Final focused run: **6 passed, 15 existing cookie deprecation warnings, exit 0, 18.05 seconds**. Ruff lint/format checks passed for the new files. Full regression is run after concurrent milestone integration, not during active shared-source edits.

## Trade-offs and limitations

- A materialized scope-first CTE makes the security boundary explicit. Its downstream full-text ranking does not use the GIN index in this implementation; the existing identity-scope index narrows candidates. No large-corpus performance claim is made.
- The exact baseline is identity substring matching within already linked evidence. It is not fuzzy PO matching or proof that a supporting source is authentic.
- Source text remains untrusted plain data. Citation resolution proves which immutable text was captured, not that its assertions are financially correct or authorized.
- There is no real mailbox/document ingestion, reranker, vector extension, or new financial decision rule.
- Day 10–12 integration adds writer/critic and durable execution without changing these read-only contracts. Stop before Day 13 unless separately authorized.

Official PostgreSQL 16 documentation inspected: https://www.postgresql.org/docs/16/textsearch-controls.html (query operators, tokenization, `ts_rank_cd`, and untrusted headline HTML considerations). No HTML highlighting is generated.

## Durable API compatibility verification

The original Day 6, 7 and 8 synthetic demo scripts now explicitly enqueue, run one worker step and fetch the completed report. The helper `app.qa.complete_synthetic_investigation` permits this only in an `ied_qa_` disposable schema; it does not intercept requests or make the HTTP API synchronous. All three scripts ran sequentially against actual PostgreSQL and returned **exit 0**: one Day 6 case, four Day 7 routes, and Day 8 missing/populated evidence plus stale-report detection. Invoice responses and empty ledgers stayed unchanged; temporary schemas were removed. Logs and report outputs remain in ignored `storage/`.


## Final combined verification

The final integrated PostgreSQL regression passed **340 tests, no skips**, exit 0,
258.64 seconds. All five private/public browser acceptance tests and frontend type
checking passed. See [Days 9?12 integration results](days-9-12-progress.md) for
recorded intermediate failures, fixes, warnings and runtime activation boundaries.
