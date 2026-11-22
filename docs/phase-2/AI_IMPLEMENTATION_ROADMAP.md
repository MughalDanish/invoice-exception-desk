# Implementation roadmap — one milestone per authorization

These are focused work packages, not guaranteed calendar days. Finish the original Day 5 first. Each milestone must run relevant unit/integration tests plus original regression suite before marking complete. Pause if safety regression or migration failure. Retain a working demo at every commit.

| Day | Deliverable | Acceptance gate |
|---|---|---|
| 5 | Original QA, benchmark, public read-only configuration, portfolio artifacts | Clean/incorrect/duplicate demo, actual test counts, no public mutations, clearly distinguish mock/live, baseline commit |
| 6 | Repository audit, typed investigation contracts, provider protocol, additive run migration, minimal LangGraph mock graph | Single NEEDS_REVIEW invoice through snapshot -> findings -> advisory report; no invoice mutation; mock mode no keys; migration round trip in isolated DB |
| 7 | Supervisor, mandatory routing and read-only tools | Four blocker classes route correctly, malformed or disallowed plan fails safely, skipped mandatory tasks caught |
| 8 | Parallel investigators and synthetic PO/receipt/email corpus | Independent branches genuinely overlap in timed test, deterministic merge, invoice and supplier scoping, missing evidence handled |
| 9 | Hybrid retrieval and evidence links | Exact SQL and FTS baseline, optional pgvector only if available, annotated recall comparison, citations resolve to source version |
| 10 | Resolution writer and critic | Unsupported claims rejected, bounded replan, insufficient evidence escalated, no AI writes |
| 11 | Local MCP tool adapter (stretch if time) | Same allowlisted read tools, schema and authorization enforcement, adversarial tool arguments rejected; no public listener |
| 12 | Durable PostgreSQL worker and checkpoint recovery | Kill/restart test, lease/fence tests, duplicate enqueue idempotency, stale result rejected, cancellation and bounded retries |
| 13 | Live Gemini investigation through an MCP client, structured writer/critic, durable budgets and call observability | Configured model genuinely selects tools over actual stdio MCP; withheld-evidence and counterfactual live synthetic smoke; grounded structured report; auth/scope/read-only and recovery gates; mock retained. See [Day 13 plan](DAY_13_LIVE_INVESTIGATION_PLAN.md) |
| 14 | Security and UI integration | Auth and public demo tests, prompt-injection corpus, escaped evidence, timeline and stale statuses, review controls unchanged |
| 15 | Evaluation harness and observability | Frozen test set, reproducible metrics, baseline vs advanced comparison, regression, redacted logs |
| 16 | Final packaging and learning review | Repeatable compose demo, README, screenshots, short walkthrough, honest case study, documented gaps |

Days 6–11 may use bounded synchronous local mock execution to establish the vertical slice, not claim durable background execution; switch enqueue/worker API on Day 12. Do not expose unbounded live calls through HTTP. Day 6 should implement only minimal graph contracts and one case, not scaffold every agent. Under the revised Day 13 scope, live Gemini and local MCP integration are required, not stretch goals. Defer second providers, rerankers and parallel live agents before safety, checkpointing or evaluation. Use a small corpus first; expand to approximately 100 scenarios only when the harness works.

## Day 13 scope revision — authorized with Day 14 on 19 November 2026

The [review and implementation plan](DAY_13_LIVE_INVESTIGATION_PLAN.md) defines
the architecture gaps, proposed single-investigator tool loop, existing-session
delegation, frozen evidence, structured assertion gate, budgets and acceptance
matrix. It supersedes the former optional live-model smoke and model-comparison
milestone. Day 13 is not complete without a separately authorized successful live
synthetic evidence test. Mocks remain required for offline development and tests,
but cannot satisfy that gate. The owner subsequently authorized both milestones;
actual outcomes are recorded in the Day 13 and Day 14 reports. Day 15 still
requires subsequent owner authorization.

Per milestone report: exact commands, exits and counts; changed files; working example; mock/live distinction; tradeoff and learning exercise; regressions and blockers; next day. Keep Phase 1 benchmark and Phase 2 results separate. Update architecture and README as code changes. No unauthorized git push, cloud provisioning or paid calls.
