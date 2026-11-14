# Owner learning track

Codex must not merely ship code. At each milestone explain the actual changed code, show the relevant file/function, explain one tradeoff, give a small exercise and let the owner verify it. Do not invent file paths before implementation.

| Day | Concepts | Hands-on owner exercise |
|---|---|---|
| 6 | Graph nodes, edges, typed state, structured outputs | Trace one wrong-total case and implement one small node |
| 7 | Supervisor vs fixed routing, tool schemas | Add a blocker route and test an invalid plan |
| 8 | Fan-out/fan-in, reducers, concurrency | Draw branch dependencies and introduce a merge conflict test |
| 9 | Embeddings, FTS, RRF, recall@k, grounding | Compare keyword vs semantic query and calculate recall manually |
| 10 | Critic loops, abstention, deterministic guards | Inject an unsupported claim and inspect rejection |
| 11 | MCP resources/tools, trust boundaries | Call a read-only tool with valid and invalid arguments |
| 12 | Checkpoints, leases, fencing, at-least-once execution | Kill worker mid-run, resume, explain why exactly-once is not guaranteed |
| 13 | Token budgets, model routing, latency and costs | Calculate cost using actual usage and compare two runs |
| 14 | Prompt injection, least privilege, stale-state safety | Write malicious evidence and prove no ledger changes |
| 15 | Ground truth, eval leakage, regression, traces | Label five unseen cases and inspect false positives |
| 16 | Deployability, engineering communication | Explain architecture and demo without reading script |

## Interview checks
Explain when normal code is superior to an agent; why a graph is not necessarily autonomous; how parallel state merges stay deterministic; why vector retrieval cannot replace exact invoice identity; how citations differ from proof; why LLM critics do not certify correctness; why checkpointing does not provide exactly-once effects; how a revision-bound approval prevents stale writes; how to measure improvement over a single LLM; how to protect tools from prompt injection; how to scale PostgreSQL workers before introducing a broker.

## Portfolio positioning
Use 'AI Invoice Exception Investigation & Approval Automation — LangGraph, FastAPI, PostgreSQL, n8n'. Show a blocked invoice, evidence timeline, chosen tools, a contradictory/missing evidence case, checkpoint recovery, human correction and fresh validation, and evaluation results. Identify synthetic data and mock/live modes. State what you personally understand and implemented with coding assistance. Do not claim client savings, production readiness, certified compliance or live integrations that were not verified. Publish original MVP first if Phase 2 takes longer than planned.

## Official references for Codex to verify against pinned versions
https://docs.langchain.com/oss/python/langgraph/overview
https://docs.langchain.com/oss/python/langgraph/persistence
https://docs.langchain.com/oss/python/langgraph/durable-execution
https://modelcontextprotocol.io/
https://github.com/pgvector/pgvector
https://ai.google.dev/gemini-api/docs/structured-output
https://www.postgresql.org/docs/16/
https://docs.smith.langchain.com/
These are starting references, not a claim of live verification in this document. Record exact consulted URLs, versions and compatibility tests during implementation.
