# Information architecture and decision journeys

This is a proposal. Production routes and permissions remain unchanged. All six
Phase 2 documents were reviewed; future workspace suggestions are conditional on
their implementation and evaluation, not instructions to implement AI now.

## Navigation and screen hierarchy

Keep a short operator navigation:

```text
Workspace
  Overview                         What needs attention?
  Invoices                         Find any document and its status
    Upload                         Existing inline task, private mode only
    Invoice review
      Review                       Current saved facts, source, failed checks, decisions
      Original extraction          Structured, read-only, unverified source output
      Activity                     Immutable decisions and field changes
      Investigation                Future, only when implemented and authorized
  Exceptions                       Held invoices, grouped/filterable by current issue
  Ledger                           Immutable posted snapshots and CSV
  Suppliers                        Registry and policy; existing list/add only
Technical / administrator          Future separate authorized area
  Investigation runs / traces / evaluations
```

Keep existing `/`, `/invoices/`, `/exceptions/`, `/ledger/`, `/vendors/` and
`/invoices/detail/?id=UUID`. The query route supports Next.js static export; do not
replace it with an unsupported runtime dynamic server route. The proposal's Original
and Activity views can be detail tabs with client URL state after approval. The
preview has seven navigation links for **comparison convenience**, not a proposal
to put Original/Activity/AI as permanent top-level production destinations.

Preserve filter/search/page context when moving from a worklist to detail and back.
Breadcrumbs show invoice/supplier identity rather than a UUID. Technical identity
remains available in a details section and copied links. Do not display inactive
AI destinations in today's production sidebar.

## Information groups in invoice review

1. **Orientation:** invoice number, supplier, exact amount/currency, invoice status,
   saved revision and current validation applicability.
2. **What prevents the next action:** failed blocking checks, source comparison,
   missing data and concise next steps. Warn about stale checks before decisions.
3. **Source and current facts:** protected document beside grouped identity, dates,
   line items and totals. “Current saved” and “Unsaved correction” differ visibly.
4. **Human decision:** required notes, current approval status, allowed next step
   and an explicit posting confirmation. Source verification precedes editing.
5. **Supporting detail:** successful checks, source snippets, prior decisions,
   immutable original extraction and complete technical evidence.

Do not put all secondary data below every passed rule. Use meaningful section
links and collapsed successful checks. Keep source evidence accessible in context;
progressive disclosure must not conceal a conflict, uncertainty or blocker.

## Progressive disclosure map

| Subject | Default business view | Expanded evidence | Complete technical view |
|---|---|---|---|
| Audit | Event-specific title, actual actor/time, meaningful transition | Notes, before/after, validation/posting result | Full event including IDs, digest, batch and attempt metadata; Copy |
| Extraction | Supplier, invoice, dates, lines, totals, uncertainty | Source snippets with honest provenance | Exact preserved payload; Copy and selection fallback |
| Validation | Neutral name, Passed/Warning/Blocks, actionable explanation | Expected vs observed, explicit source link when available | Original code/severity/raw evidence |
| File | Filename, size/type, received time, open/download | Ingestion source | SHA-256, record ID |
| Error | Task-specific explanation and safe recovery | Request conflict/stale state context | Structured error code; no secrets or arbitrary backend dump |
| Supplier | Name, approval, currency, review threshold | Policy explanation | Existing identifiers only if useful; no invented editing control |
| Future AI | Advisory summary, evidence, missing facts, applicability | Findings and responsibility timeline | Authorized traces, tool/model calls and evaluation telemetry |

No data is removed from storage, audit records or backend responses. Presentation
adapters are deterministic translations. Unknown types retain a safe fallback and
all original evidence rather than being omitted from the UI.

## Five operator journeys

### A. Process a clean invoice

Upload → explicit received/extraction result → direct invoice link → concise current
validation summary → inspect source → explicit Post if eligible → immutable posted
state and ledger link. Existing clean invoices do not gain a new mandatory approval
step merely for visual consistency. Deduplicated uploads link the original record.
No percentage, finish time or automatic posting is invented.

### B. Resolve incorrect information

Exception queue → leading blocker → original/current/source comparison → edit
verified fields → save correction and reason → new revision with no current checks
→ revalidate → required current-revision approval → explicit Post. Preserve typed
decimal strings, do not replace total merely because arithmetic suggests a value.
A concurrent conflict reloads the latest saved state and asks the operator to
review it. Do not silently resubmit an approval or post after HTTP 409.

### C. Investigate a duplicate

Show normalized supplier/invoice match explanation and relevant peer(s), including
status and changed amounts where the authorized API actually supplies them. A
different amount does not clear identity duplication. Provide prior-invoice links
only when authorized IDs are available; otherwise disclose the existing evidence
and identify the missing richer comparison as an API dependency. Verify original
record → choose Reject with reason where appropriate. No “Ignore duplicate and
post” button. Exact-file deduplication and business duplicate holds are distinct.

### D. Review history

Open Activity → identify actor and timestamp → read correction before/after and
recorded reason → inspect actual validation/review/post sequence → expand technical
evidence if needed. Keep source event order and stable identity. Repeated delivery
events may be compacted visually only with a count and access to every record.
Distinguish original revision, current saved revision and approved historical
revision; “extracted” is never a synonym for “verified”.

### E. Manage suppliers

Find registry entry → read approval/currency/threshold → use existing authorized
registration for an absent supplier → return to held invoice → revalidate → required
human review. Existing supplier update/delete, supplier history pages and multi-role
policy approval do not exist. Do not draw functional Edit controls without an
approved contract. Investigations may read policy later, never modify it.

## Future investigation workspace: advisory only

Keep the invoice status and validation state above the investigation region. On
desktop use three bounded regions; on smaller screens put summary and required
human step first, findings/evidence next, execution details last.

| Region | Business content | Future contract / constraint |
|---|---|---|
| Investigation header | Run state, applicability, source invoice revision, actual progress | Source payload hash/batch/version bind the report; do not infer percent from node count |
| Strategy / responsibilities | “Check duplicate identity”, “Compare supplier history”, “Find source evidence” | Explain selected tasks and mandatory checks; no opaque agent role names required |
| Findings | Supported, conflicting or insufficient claims; concise evidence-grounded summaries | No hidden chain-of-thought, invented confidence or claim without resolvable citation |
| Evidence panel | Source document/version, excerpt and available location; related records | Invoice/supplier-scoped reads, escaped untrusted text; missing evidence is explicit |
| Recommendation | Proposed resolution, supporting facts, restrictions, remaining uncertainty | Advisory action allowlist excludes APPROVE and POST |
| Human decision region | Existing correction/revalidation/approval/post flow, clearly separate | Acknowledging report is not financial approval; never prefill authorization from AI |
| Execution timeline | Named task, waiting/running/completed/failed, parallel branches and recovery | Only actual persisted execution events; expandable allowlisted-tool summaries |
| Technical observability | Models, calls, latency, retries, checkpoints, tokens/cost, evaluations | Separate operator-authorized view; unknown values remain unknown, estimates labelled |

Example future applicability language:

- Queued / Running: actual status and start time, cancel only when API supports it.
- Waiting for evidence: identify required material without implying autonomous
  supplier outreach. WAITING_INPUT is optional in the spec; do not require it now.
- Completed: “Advisory report for revision N”; deterministic holds remain visible.
- Failed / Cancelled: sanitized reason, actual retry policy, safe explicit retry.
- Out of date: report tied to a different revision/hash/batch; preserve historical
  view and explicitly rerun. Never display stale advice as current verification.
- Insufficient evidence: supported result, missing facts and human next step,
  without invented resolution.

The initial graph on roadmap Day 6 is a minimal typed mock vertical slice, not a
production workspace. Supervisor routing, parallel branches, retrieval, critic,
durability and observability arrive in their separately authorized milestones.
Day 14 UI integration must use actual contracts. Public mode may eventually show
sanitized seeded reports only; no jobs, live model calls or private evidence access.

## Boundary between operator and technical experiences

Finance operators need outcome, facts, missing evidence and decision authority.
They do not need token charts or checkpoint IDs in the review form. Administrator
views can expose sanitized traces and actual cost inputs, but the current app has
one local operator, not a role/SSO system. “Administrator” is a future information
audience, not an implemented security role. Reuse current operator authorization
until a separately approved model exists; keep public and integration boundaries.
No external telemetry/tracing service is enabled by these recommendations.
