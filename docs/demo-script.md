# Two-minute operator demonstration

Use only bundled synthetic documents and `AI_MODE=mock`. The private dashboard is
http://localhost:3000; sign in with the operator values in the ignored `.env`.
No account/password belongs in a screenshot or recording. Start recording after login.

For a fresh run, use the isolated browser scenario (it never resets the owner's DB):

```powershell
cd frontend
npm.cmd run test:e2e
```

For the repeatable API demonstration in the existing private stack:

```powershell
docker compose exec -T backend python -m app.smoke
```

This safely returns existing terminal invoice/ledger IDs when run again. A fresh
recording of corrections requires a new isolated demo database; do not silently
edit or delete posted examples. The browser acceptance runner supplies that fresh
schema automatically. The current public snapshot intentionally preserves a
wrong-total invoice that has not been corrected, so visitors can inspect the hold.

| Time | Show / explain |
|---|---|
| 0:00–0:15 | Overview: "This is an independent synthetic demonstration. The goal is to catch mistakes before an internal ledger entry is created." |
| 0:15–0:35 | Upload clean-001. Extraction is a deterministic mock. Show READY_TO_POST, then explicitly Post. No automatic posting or payment occurs. |
| 0:35–0:55 | Upload wrong-total: subtotal 2000 + tax 300, stated total 2500. Show TOTAL_MISMATCH and expected/observed values. Post is unavailable; direct API posting is also blocked. |
| 0:55–1:15 | Compare source, correct total to decimal string 2300.00, save notes, Revalidate, Approve current revision, then Post. Explain that approval cannot waive a rule. |
| 1:15–1:35 | Upload duplicate-altered. Same supplier/invoice identity is caught despite changed bytes/amount. Approval/post remain blocked; reject it with a reason. |
| 1:35–1:50 | Audit tab: before/after correction, operator, revision and posting. Ledger CSV contains only posted snapshots. |
| 1:50–2:00 | Show the benchmark: 16 scripted cases; live AI accuracy NOT RUN. Stack: Next.js, FastAPI, PostgreSQL, optional n8n. No ERP writes/payments. |

## Saved public walkthrough

[`demo-walkthrough.webm`](demo-walkthrough.webm) is a real silent browser recording
of anonymous public navigation: overview, blocked total, synthetic source, audit,
supplier list, ledger and mobile layout. It does not show corrections/approvals
because public mode cannot perform them. It is not narrated or advertised as a
two-minute operator recording; the table above is the owner's recording script.

## Portfolio screenshots

- [Public overview](screenshots/public-overview.png)
- [Wrong-total detail and rule](screenshots/total-mismatch.png)
- [Synthetic audit history](screenshots/audit.png)
- [Mobile read-only overview](screenshots/public-mobile.png)

The n8n workflow JSON is importable and its internal intake/replay nodes were
executed locally. Gmail/Telegram are disabled and not presented as live connected
services. Use its actual imported canvas for a future owner-configured screenshot;
do not substitute a diagram and label it a connected Gmail execution.
