# Day 9 learning guide

Start with `backend/app/modules/evidence/search.py`. Retrieval has three separate responsibilities: establish an authorized identity scope, rank candidate sources, and return exact provenance. Keeping them separate makes it harder for a ranking change to leak another invoice's documents.

`retrieve()` derives supplier identity from the database invoice. Its parameterized materialized SQL first filters invoice UUID **and** supplier key and picks the latest row per source UUID. Only those rows enter exact matching or full-text ranking. Never move authorization into a Python filter applied after a global top-k search: unrelated rows would already have influenced ranking and potentially escaped into logs or results.

Exact SQL finds identity text. PostgreSQL full-text search tokenizes words and stems variants, so “receipts” can match “receipt”; it does not understand arbitrary semantic similarity. Embeddings encode text into vectors that support approximate similarity. This milestone deliberately uses no embeddings because pgvector is unavailable; a dependency is not required to demonstrate an honest lexical baseline.

Study `reciprocal_rank_fusion()`: each list contributes `1/(60+rank)` rather than its raw score. SQL identity scores and full-text scores have different meanings; fusing ranks avoids pretending they are directly comparable. A document appearing near the top of both rankings gains weight. Fraction arithmetic and a stable citation-ID tie-break make results independent of branch ordering.

Then inspect `Citation.exact_location()` and `RetrievalSnapshot.enforce_scope()` in `evidence/schemas.py`. These are immutable boundary contracts. They reject fabricated hashes, invalid character locations, cross-scope sources, duplicate sources and fused citations absent from the captured candidates. A citation is a source reference, not proof that an email's claim is true. Financial validation remains separate.

`evidence/routes.py` resolves a historical source version through cookie-authenticated GET. It receives an invoice UUID, source UUID and positive version, derives current supplier scope on the server and returns the exact source. There is no source-writing, approval or posting endpoint in this module. Study how `Cache-Control: no-store` avoids storing private evidence in intermediary caches.

To modify retrieval independently, change only the vocabulary in `capture_retrieval()` or scoring logic in `retrieve()`, keep scope predicates intact, and bump the algorithm version if behavior changes. Do not modify the immutable source data or financial business rules to improve an evaluation score. Changes to ranking naturally change the captured retrieval snapshot and can make earlier reports stale.

Run the synthetic diagnostic from the repository root:

```powershell
.venv/Scripts/python.exe scripts/run_retrieval_evaluation.py
```

It reads the existing local database connection privately, creates random disposable schemas, ingests only original synthetic test fixtures, adds the separate annotated evidence corpus, executes real PostgreSQL searches and removes the schemas. Its ignored JSON output contains aggregate metrics, not keys or live invoice contents. Full regression command: `.venv/Scripts/python.exe scripts/dev.py test --postgres`.

Read `backend/tests/test_evidence_retrieval.py` for negative tests: wrong supplier, wrong invoice, malicious query operators, old/new source versions, invented references and result truncation. These protect boundaries; they do not merely mirror the success path.

Exercise: add a synthetic source that describes a relevant delivery without printing the invoice number. Before running, predict exact SQL recall and FTS recall. Calculate recall manually as `relevant sources retrieved / all labeled relevant sources`. Then add more than five distractors and observe whether the original three-source diagnostic overstated ranking quality. Keep evaluation labels out of retrieval inputs. Finally explain why 100% recall on six hand-authored examples is not evidence of production reliability.
