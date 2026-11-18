# Day 10: resolution writer and critic

The investigation now separates collecting facts from recommending an operator action. A writer proposes a strict `ResolutionDraft`; a critic checks it before a report can be published. Both remain offline scripted components. This demonstrates orchestration and safety boundaries, not live model reasoning quality.

## Files and responsibilities

- `backend/app/modules/investigation/resolution.py`: canonical mock draft, deterministic critique, provider extension hooks and safe fallback.
- `backend/app/modules/investigation/resolution_schemas.py`: small immutable critic outcomes and report review metadata. It deliberately does not import the investigation schemas, avoiding a circular import.
- `backend/app/modules/investigation/graph.py`: `resolution_writer` and `resolution_critic` nodes after the three-worker join, conditional repair edges and final report construction.
- `backend/app/modules/investigation/schemas.py`: optional `resolution` metadata on the report, keeping older stored reports readable.
- `backend/tests/test_investigation_resolution.py`: altered amounts, forged citations, stale bindings, omitted evidence, malformed output, bounded repairs and escalation.

## Follow the data

`frozen snapshot -> supervisor -> parallel workers -> deterministic merge -> writer -> critic -> report`

The existing worker gate still compares every finding with the allowed evidence-backed finding. The writer receives only those verified findings, not a database session or mutation tools. Its draft carries the same source revision, payload hash and validation batch. The critic compares the draft against the finite reviewed mock vocabulary and exact findings. This rejects changed decimal strings as well as unsupported prose; it does not try to infer financial truth using a regular expression.

An optional provider critic may reject an otherwise valid draft, but cannot accept a draft rejected by code. A model opinion is therefore an additional check, never the final authority.

## Bounded repair and abstention

Study `write_resolution`, `critic` and `next_resolution` inside `build_graph`. The initial draft plus two repairs gives a maximum of three attempts. Only sanitized error codes return as feedback. Read tools and investigators do not repeat during repairs. Graph state records the current attempt, validated draft and critic outcome for checkpoint recovery.

After exhaustion the report uses a canonical safe draft, preserves the original verified findings and requests human evidence. Rejected provider text is never copied into the published report. Malformed drafts are reduced to `None` before checkpointing; raw malformed output is not logged.

All current mock recommendations remain `REQUEST_EVIDENCE`: original-document authenticity and reconciliation are still unverified. A recorded total mismatch does not establish whether the source invoice or extraction is wrong. No report approves a supplier, changes an amount or posts a ledger entry.

## Trade-off and independent changes

The mock critic uses exact canonical equality. It is deliberately stricter than a future natural-language writer: harmless paraphrases are rejected too. This makes grounding demonstrable with deterministic tests, but it is not a semantic verification model. Add a new reviewed template and its adversarial tests together before widening this boundary.

To change recommendation wording, edit `canonical_draft`. To change loop limits, edit `MAX_RESOLUTION_ATTEMPTS` and review the graph recursion budget and checkpoint compatibility. To add provider behavior, implement `write_resolution(snapshot, findings, attempt, feedback)` and optionally `critique_resolution(snapshot, findings, candidate)`; neither receives write capabilities. Changes to financial approval belong to the existing deterministic workflow, not these hooks.

## Run and learn

From the repository root:

```powershell
.venv/Scripts/python.exe -m pytest -q backend/tests/test_investigation_resolution.py -c backend/pyproject.toml
.venv/Scripts/python.exe scripts/dev.py test --postgres
```

Exercise: make a test provider replace `2300.0000` with `2300.0001` in a finding. Confirm `UNSUPPORTED_CLAIM`, three attempts, and a final safe evidence request containing the original amount. Then return a valid draft on attempt two and confirm that investigators ran only once. Explain why an always-approving model critic cannot bypass the deterministic gate.
