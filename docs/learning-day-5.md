# Day 5 learning review: establish a safe, measurable baseline

The next incomplete roadmap milestone was Day 5. LangGraph nodes, agent plans,
retrieval, critics and checkpoints belong to later milestones and are not present
yet. A passing baseline gives those changes something concrete to preserve.

## A read model separates display from authority

`backend/app/qa.py::public_export` builds a synthetic scenario in a new PostgreSQL
schema through the actual API, then exports a finite set of invoice/rule/audit/
ledger responses. `backend/app/modules/public_demo.py::create_public_router`
serves that projection. The financial source of truth remains PostgreSQL in the
private operator workflow. The public process is a display surface over reviewed
synthetic artifacts, not another financial writer.

This is a small use of separating write and read models: the public view can
survive hosting restarts and cannot accidentally select private DB rows. The
tradeoff is freshness. Clicking Refresh reloads a frozen snapshot, not the private
ledger. To change the portfolio data, explicitly regenerate, review and redeploy.

## A security invariant belongs at the execution boundary

`backend/app/core/middleware.py::PublicReadOnly` denies every method except
GET/HEAD/OPTIONS before consuming request bytes. `app.main.create_app` also avoids
mounting operator/integration routers or constructing an engine in public mode.
This gives two independent controls: mutations cannot reach a handler, and no
financial writer is available in that application instance.

The frontend reads `/api/v1/config` and hides write controls. That improves clarity
but is not authorization: browser HTML can be modified. `test_public_demo.py`
explicitly sends POST/PATCH/DELETE requests anyway, including correct configured
credentials, and checks 403. A spy raises if public startup tries to build a DB
engine. This pattern is also the reason Phase 2 tools must lack financial mutation
capabilities rather than merely receive a prompt saying "do not post".

## A mock score measures software, not model reasoning

`backend/app/qa.py::benchmark` exercises all original 16 submissions through upload,
mock processing, detail, a real posting attempt, and a ledger count. The answer
key deliberately supplies the mock's extraction. Comparing that output with the
same key is an adapter-contract check, not independent field extraction accuracy.
The report therefore marks live model quality and extraction accuracy NOT RUN.

There are two separate confusion matrices:

- **Workflow containment:** 11 submissions should not create a new ledger entry;
  5 clean submissions should. Includes exact file duplicate and extraction failure.
- **Rule validation:** 9 labeled blocking cases and 5 clean cases, excluding the
  exact duplicate returned at ingestion and the unusable extraction result.

Precision = TP / (TP + FP), recall = TP / (TP + FN). Here the dataset is small,
synthetic, deterministic, and reused during development. Even a perfect score
does not predict performance on unseen supplier documents.

Latency uses `time.perf_counter`, the entire synchronous request sequence, and the
nearest-rank percentile: sorted value at `ceil(n * p)`. Schema setup and duplicate
reference seeding are explicitly outside that interval. With only 16 observations,
p95 is the maximum; it is not a production SLO, load test or live-provider latency.

## Owner exercise

1. Open `docs/benchmarks/phase-1-mock.csv`. Count the held and clean rows and
   independently reproduce TP/FP/FN/TN. Explain why duplicate-copy is not a rule
   engine positive and why extraction-failure is not a field-accuracy observation.
2. Open the public preview and try a POST to `/api/v1/vendors` using browser tools.
   Verify HTTP 403 and the unchanged supplier count. Explain why changing a disabled
   button cannot grant a financial capability.
3. In the private dashboard, upload `wrong-line.pdf`, observe the blocking rule and
   the disabled Post action. Describe why a future AI explanation cannot remove
   that blocker: the operator must correct, revalidate, approve the current revision
   and pass the existing transactional post checks.

Next, after authorization, Day 6 introduces typed investigation state and a minimal
mock graph over one immutable invoice snapshot. It must retain this baseline and
never modify an invoice, vendor, approval or ledger row.
