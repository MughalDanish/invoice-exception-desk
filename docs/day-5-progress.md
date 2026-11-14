# Day 5 milestone report — verified Phase 1 baseline

Completed locally on 14 November 2026 (Asia/Karachi). No cloud deployment, Git push,
live model inference or real financial document processing occurred.

## Why this milestone

All six newly supplied Phase 2 documents were read and preserved byte-for-byte in
`docs/phase-2/`. The original specification, implementation brief, architecture,
Day 1–4 reports and current repository were inspected. The roadmap explicitly
requires **Day 5 before Day 6**. The starting tree was clean on
`feature/invoice-exception-desk`, baseline commit `08cdc32`. Only Day 5 was authorized
and implemented. No LangGraph dependency, investigation module, new agent, MCP tool,
retrieval corpus, worker or checkpoint schema was added.

After the clean baseline commit, the Phase 2 branch is prepared as instructed by
`AI_UPGRADE_START_HERE.md`; creating that branch does not implement Day 6.
**Stop here: Day 6 requires the owner's confirmation.**

## Previous milestone verification

The prior reports' counts were not assumed. Actual reruns before UI changes:

- Full Linux/PostgreSQL baseline: **143 passed**, no skips, exit 0, one existing
  Starlette/httpx deprecation warning. The report's original 142 became 143 after
  the separately committed loopback CORS regression case.
- Original Playwright operator suite: **2 passed**, exit 0, in 1.4 minutes.
- Models, all four migrations, routes, auth, strict schemas, dependencies and
  frontend static-export configuration were inspected. No dirty work was reset
  or stashed, and no sibling application was changed.

## Delivered and changed files

| Area | Files / behavior |
|---|---|
| Public read boundary | `backend/app/core/config.py`, `middleware.py`, `main.py`: public mode requires mock extraction, registers only finite read routes, constructs no DB engine, and denies mutations before body parsing. Auth cannot bypass it. `/api/v1/config` exposes mode only. |
| Public read model | `backend/app/modules/public_demo.py`, `fixtures/public-demo.json`: 15 unique synthetic invoices from the original 16 submissions, vendors, rules, synthetic audit, one explicitly posted clean ledger snapshot. Bundled PDFs are checked against fixture hashes; no private upload or DB is read. |
| Reproducible QA | `backend/app/qa.py`: random-schema isolation, real API upload/process/post attempts, separate workflow/rule denominators, mock timings, JSON/CSV output and public export. `scripts/write_benchmark_report.py` renders measured results. |
| Safety regression | `backend/tests/test_public_demo.py`: 38 cases covering anonymous/operator/integration mutations, future-route denial, no DB construction, no body parsing, read model immutability/restart, source scoping, bad origins, live-provider refusal and altered fixture payload rejection. |
| Dashboard | API transport and desk/list/detail/ledger/vendor components consume server mode; anonymous read-only entry, visible synthetic banner, disabled fields, hidden financial controls and no embedded credentials. Writable controls remain revision-bound as before. |
| Public browser QA | `frontend/playwright.public.config.ts`, `frontend/public-tests/public.spec.ts`, `scripts/public_api.py`: credential-free scenario on isolated ports, also runnable against built containers using `PUBLIC_PREVIEW=true`. |
| Deployment preparation | `render.yaml`, `infrastructure/compose.public.yml`, `compose.vm.yml`, `Caddyfile`, infrastructure README and `docs/deployment.md`: Render static/API preparation, separate local public stack, private-VM HTTPS guidance, optional Neon instructions, free-host restrictions and reset/backup policy. |
| Portfolio and learning | `docs/benchmark.md`, `docs/benchmarks/phase-1-mock.{json,csv}`, four real screenshots, `docs/demo-walkthrough.webm`, `docs/demo-script.md`, `docs/portfolio.md`, `docs/learning-day-5.md`, architecture and README updates. `.gitattributes` treats the recording as binary. |
| Source specification | All six original Phase 2 files under `docs/phase-2/`; verified equal to the supplied Downloads files. |

Existing Gemini extraction code, ORM models, migrations, n8n workflow, all original
PDFs and `fixtures/answers.json` are unchanged relative to `08cdc32`. No migration
was needed: the schema head remains `0004_integration_delivery`.

No dependency inputs were changed or new runtime packages added. The tested
versions include container Python 3.12.16, FastAPI 0.162.6, Pydantic 2.14.3,
SQLAlchemy 2.0.57, Alembic 1.20.1, psycopg 3.3.9, google-genai 1.75.0, pytest 9.2.0,
Next.js 16.4.6, React 19.3.1, TypeScript 5.9.3 and Tailwind 4.3.5. PostgreSQL is
the existing 16.16 container. Complete Python and npm versions remain pinned
in `backend/requirements.txt` and `frontend/package-lock.json`.

## Exact checks and observed results

Every completed command below exited 0. The commands were run from the repository
root unless noted; Docker operations used the existing local engine.

| Command | Observed result |
|---|---|
| `docker compose exec -T backend python -c "import os,pytest; os.environ['TEST_DATABASE_URL']=os.environ['DATABASE_URL']; raise SystemExit(pytest.main(['-q','--tb=short','-p','no:cacheprovider']))"` | Baseline 143 passed; Day 5 full regression **181 passed**, no skips, in 51.07 seconds. One existing deprecation warning. Includes real PostgreSQL migration round trip, concurrency, rollback and financial invariants. |
| `npm.cmd run test:e2e` in `frontend/` | Baseline 2 passed; updated writable UI **2 passed**, in 1.0 minute. Clean posting, correction/revalidation/current approval/posting, duplicate rejection, CSV, audit, supplier and mobile/sign-out. |
| `../.venv/Scripts/python.exe -m pytest tests/test_public_demo.py -q --tb=short` in `backend/` | **38 passed**. Rerun after assigning valid operator/integration credentials to the public test app, confirming even those credentials cannot authorize public writes. |
| `npm.cmd run test:e2e -- --config playwright.public.config.ts` in `frontend/` | **1 passed** against the host preview, in 43.6 seconds. No DB, provider key or login. |
| Same public command with `PUBLIC_PREVIEW=true` | **1 passed** against actual nginx/static-export + public FastAPI containers in 26.6 seconds; the same scenario is repeated, not counted as another independent case. Refreshed screenshots and silent video captured. |
| `npm.cmd run typecheck` | Passed. Linux Next.js static-export builds also passed for private and public API URLs; all six application routes generated. |
| `node scripts/check_dashboard.mjs` | Refreshed private nginx/static dashboard passed login, existing data, invoice detail navigation and mobile layout; no browser errors or financial writes. |
| `docker compose build backend` and `docker compose --profile dashboard up -d --build --no-deps frontend` | Built/started the private stack; no data-volume replacement. |
| `docker compose -f infrastructure/compose.public.yml up -d --build` | Built/started an independent local public project on 3002/8002, with no DB/secret/upload mount. API health reports `public_demo`, `database=not_used`, mock mode. Direct POST /vendors returned structured 403. |
| `docker compose -f infrastructure/compose.public.yml config --quiet` | Public configuration valid. |
| `docker compose -f docker-compose.yml -f infrastructure/compose.vm.yml --profile dashboard --profile automation config --quiet` with example domain environment values | VM overlay valid; no VM/certificate was created. Caddy routing/TLS has not been exercised on a VM. |
| `docker compose exec -T backend python -m app.smoke` | Passed: original two ledger IDs returned, corrected revision 2, rejected duplicate, blocked repeat business duplicate, verified source bytes/audit, two CSV rows. No additional ledger entry. |
| QA commands below | 16/16 fixture contracts passed; 16 isolated case schemas plus an isolated public-export schema; existing demo untouched. |
| Ruff check/format, `pip check`, `git diff --check`, original-fixture/code diff and six-document byte comparison | Passed. Original fixture bytes, extraction adapter, migrations and original financial model unchanged. |

QA reproduction commands (the local run also bind-mounted the current QA source
while its image was being refreshed):

```powershell
docker compose build backend
docker compose run --rm --no-deps -T -v ./docs/benchmarks:/results backend python -m app.qa benchmark --output /results/phase-1-mock.json
docker compose run --rm --no-deps -T -v ./fixtures:/exports backend python -m app.qa public-export --output /exports/public-demo.json
.\.venv\Scripts\python.exe scripts/write_benchmark_report.py
```

On Linux, bind-mounted output directories must be writable by the container user;
use the host UID/GID for the one-off QA container or write under `/tmp` and copy
artifacts out. No arbitrary application schema is dropped: generated names are
`ied_qa_<random UUID>` and cleanup runs in a finally block.

The private Windows test API logged one non-failing asyncio socket-reset callback
on an aborted browser connection, as in Day 4. Browser assertions and cleanup passed.
No financial or authentication test assertion failed. A first attempt to parse
Render YAML with Python found no PyYAML dependency; none was added solely for that
check. The Blueprint was reviewed against official docs, but no remote Render
validation/deployment is claimed. Compose YAML was validated by Docker itself.

## Measured Phase 1 results, not Phase 2 AI scores

Latest recorded run: 2026-11-14T07:13:49.181556Z. Five clean, three arithmetic,
three duplicate submissions, two unapproved supplier, two missing-field and one
explicit extraction-failure case; 15 distinct byte hashes.

- Workflow containment: TP 11, FP 0, FN 0, TN 5. All 11 unsafe/repeated/failed
  submissions prevented a new ledger row; all five clean submissions posted explicitly.
- Rule-only subset: 14 cases, TP 9, FP 0, FN 0, TN 5, excluding exact-file deduplication
  and unusable extraction. Expected blocker codes present in all labeled cases.
- Mock timing: p50 160.523 ms, p95 842.362 ms over 16 upload-to-post-attempt API
  sequences, excluding schema/reference setup. Not a load test or live-model SLO.
- Live field accuracy, Gemini reasoning quality/latency/token/cost measurements:
  **NOT RUN**. Scripted answers are not independent extraction ground truth.

See `docs/benchmark.md` for denominators, nearest-rank definition, all cases,
provenance, command, JSON/CSV artifacts and limitations. These results are not a
100-scenario Phase 2 corpus, unseen production benchmark or client savings claim.

## Engineering concepts and owner exercise

`docs/learning-day-5.md` connects real functions to three ideas: read models separate
public display from financial authority; authorization belongs at an execution
boundary rather than in hidden buttons/prompts; mock scores establish software
contracts without proving AI quality. It explains the freshness tradeoff, TP/FP/FN
and percentile calculation, and gives a small exercise to reproduce counts and
prove an anonymous POST remains forbidden. No graph concept is falsely claimed as
implemented in this prerequisite milestone.

## Working demo and limitations

- Private operator: http://localhost:3000, existing `.env` credentials, existing
  data retained. Public read-only preview: http://localhost:3002, no login.
- Real PostgreSQL financial safeguards remain authoritative. Explicit posting only;
  no new automatic financial action, supplier contact, payment or ERP integration.
- Public mode serves a reviewed static projection; private ledger changes do not
  automatically update it. This security/storage tradeoff is documented. It does
  not need Neon at runtime; separate private Neon setup guidance is prepared.
- Gemini is SDK-tested offline; no live model call was authorized or made. Gmail
  OAuth/Telegram remain unconnected. The n8n JSON is unchanged and its prior Day 4
  internal-node execution is documented separately; Day 5 reran integration API
  regression tests rather than claiming a new external-account test.
- The saved WebM is an actual **silent public navigation recording**, not a narrated
  two-minute financial-edit video. The two-minute operator script and fresh-schema
  instructions are provided. A PDF viewer can be blank in headless captures; the
  source download is verified byte-for-byte and available as the fallback.
- Render Blueprint, optional Neon connection and VM/Caddy TLS are preparation,
  not live infrastructure. Free-host limits were checked against official sources
  and linked in `docs/deployment.md`. No services were provisioned or charged.
- GitHub publication still waits for restored access. No secrets/private data are
  included in the portfolio dataset or recording. No public writes are enabled.

Next authorized work, **only after confirmation**: Day 6 repository audit, typed
investigation/provider contracts, additive run migration and a minimal mock graph
over one NEEDS_REVIEW snapshot, with no financial mutations.
