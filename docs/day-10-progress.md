# Day 10 progress: resolution writer and critic

## Implemented behavior

The real LangGraph now runs `resolution_writer -> resolution_critic` after its existing parallel investigation join. Strict drafts contain verified findings and source bindings. The deterministic critic rejects unsupported prose or altered exact monetary claims, forged or changed citations, omitted findings/gaps, mismatched revision/hash/batch and unsupported actions. An optional provider critic may reject but cannot override these checks.

The graph permits the initial draft and at most two repairs. Exhaustion publishes a safe canonical evidence request, never rejected provider prose. Missing or unreconciled evidence also escalates to human review. Existing financial validators, approval rules and ledger behavior remain authoritative and unchanged. Investigations have no financial write tools.

This is an offline scripted implementation. No live model call or live reasoning-quality evaluation was performed. Canonical equality deliberately rejects even harmless paraphrases; a future live writer needs a separately evaluated semantic claim contract. Current original documents remain unreconciled, so recommendations conservatively request evidence.

## Changed files

- `backend/app/modules/investigation/graph.py`
- `backend/app/modules/investigation/resolution.py`
- `backend/app/modules/investigation/resolution_schemas.py`
- `backend/app/modules/investigation/schemas.py` (optional review metadata, integrated with Days 9–12)
- `backend/tests/test_investigation_resolution.py`
- `docs/learning-day-10.md`
- `docs/day-10-progress.md`

The graph accepts an optional checkpointer for Day 12. Typed state includes attempt count, bounded validated draft and sanitized critic outcome; malformed drafts are not retained. No new dependency is needed for Day 10.

## Verification

Focused lint passed with `python -m ruff check` over the Day 10 modules and tests.

```powershell
.venv/Scripts/python.exe -m pytest -q backend/tests/test_investigation_resolution.py -c backend/pyproject.toml --tb=short
```

Actual result after shared schema integration: **15 passed in 0.58 seconds, exit 0**. The tests exercise all six graph scenarios and nine parameterized draft attacks without a database or network model call. Combined backend regressions, migrations and durable-worker recovery checks belong to the integrated Days 9–12 verification; these focused results do not imply those checks passed.

See [the learning guide](learning-day-10.md) for the writer/critic boundary, retry flow, maintenance points and an unsupported-amount exercise. Days 9–12 were authorized together; stop before Day 13.


## Final combined verification

The final integrated PostgreSQL regression passed **340 tests, no skips**, exit 0,
258.64 seconds. All five private/public browser acceptance tests and frontend type
checking passed. See [Days 9?12 integration results](days-9-12-progress.md) for
recorded intermediate failures, fixes, warnings and runtime activation boundaries.
