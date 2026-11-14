"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { binary, download, request, time, title, type Detail, type Event, type Payload } from "@/lib/api";
import { Badge, Heading, Notice, useDesk } from "./desk";

const fields: (keyof Payload)[] = ["vendor_name", "vendor_tax_id", "invoice_number", "invoice_date", "due_date", "currency", "subtotal", "tax_rate", "tax_amount", "total"];
export function InvoiceDetail() {
  const id = useSearchParams().get("id"); const { token, readOnly, fail } = useDesk();
  const [invoice, setInvoice] = useState<Detail | null>(null); const [draft, setDraft] = useState<Payload | null>(null);
  const [events, setEvents] = useState<Event[]>([]); const [preview, setPreview] = useState(""); const [previewError, setPreviewError] = useState("");
  const [error, setError] = useState(""); const [message, setMessage] = useState(""); const [pending, setPending] = useState(""); const [notes, setNotes] = useState("");
  const [tab, setTab] = useState("review"); const [loading, setLoading] = useState(true);
  const validId = !!id && /^[a-f0-9-]{36}$/i.test(id);
  const load = useCallback(async () => {
    if (!validId) { setLoading(false); return; }
    const [row, audit] = await Promise.all([request<Detail>(token, `/invoices/${id}`), request<Event[]>(token, `/invoices/${id}/audit`)]);
    setInvoice(row); setDraft(row.current_data ? structuredClone(row.current_data) : null); setEvents(audit); setLoading(false);
  }, [token, id, validId]);
  useEffect(() => { let mounted = true; void load().catch(e => { if (mounted) { setError(fail(e)); setLoading(false); } }); return () => { mounted = false; }; }, [load]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!validId) return;
    let active = true, url = "";
    binary(token, `/invoices/${id}/file`).then(blob => { if (active) { url = URL.createObjectURL(blob); setPreview(url); } }).catch(e => { if (active) setPreviewError(fail(e)); });
    return () => { active = false; if (url) URL.revokeObjectURL(url); };
  }, [id, token, validId]); // eslint-disable-line react-hooks/exhaustive-deps
  async function action(name: string) {
    if (!invoice) return;
    setPending(name); setError(""); setMessage("");
    try {
      const body: Record<string, unknown> = { expected_revision: invoice.revision };
      let path = `/invoices/${id}/${name}`, method = "POST";
      if (name === "save") {
        const changes = Object.fromEntries(Object.entries(draft || {}).filter(([key, value]) => JSON.stringify(value) !== JSON.stringify(invoice.current_data?.[key as keyof Payload])));
        body.changes = changes; body.notes = notes; path = `/invoices/${id}`; method = "PATCH";
      }
      if (name === "approve" || name === "reject") { path = `/invoices/${id}/review`; body.decision = name === "approve" ? "APPROVE" : "REJECT"; body.notes = notes; }
      if (name === "process" || name === "retry") { path = `/invoices/${id}/process${name === "retry" ? "?retry=true" : ""}`; }
      const result = await request<{ status?: string }>(token, path, { method, body: name === "process" || name === "retry" ? undefined : JSON.stringify(body) });
      await load();
      setMessage(name === "save" ? "Corrections saved. Revalidate, then approve the current revision before posting." : result.status === "EXTRACTION_FAILED" ? "Extraction failed. See the attempt details below." : `${title(name)} completed. The latest invoice state is shown below.`);
    } catch (e) { setError(fail(e)); await load().catch(() => {}); }
    finally { setPending(""); }
  }
  if (!validId) return <Notice error>Choose an invoice from <Link href="/invoices/">All invoices</Link> to open its details.</Notice>;
  if (loading) return <div role="status" className="empty">Loading invoice…</div>;
  if (!invoice) return <Notice error>{error || "Invoice unavailable"} <Link href="/invoices/">Back to invoices</Link></Notice>;
  const terminal = readOnly || ["POSTED", "REJECTED"].includes(invoice.status), processing = !readOnly && ["RECEIVED", "EXTRACTING", "EXTRACTION_FAILED"].includes(invoice.status);
  const dirty = JSON.stringify(draft) !== JSON.stringify(invoice.current_data);
  const blockers = invoice.validations.filter(rule => !rule.passed && rule.severity === "BLOCKER");
  const checked = invoice.validated_revision === invoice.revision;
  const approved = invoice.reviews.some(review => review.revision === invoice.revision && review.decision === "APPROVE");
  const disabled = !!pending || terminal || processing || dirty;
  function field(key: keyof Payload, value: string) { setDraft(old => old ? { ...old, [key]: value === "" ? null : value } : old); }
  return <><Link href="/invoices/" className="back-link">← All invoices</Link><Heading eyebrow={`INVOICE · REVISION ${invoice.revision}`} title={invoice.current_data?.invoice_number || invoice.filename} subtitle={invoice.current_data?.vendor_name || "Waiting for extraction"}><Badge status={invoice.status}/><button disabled={!!pending} onClick={() => { setError(""); void load().catch(e => setError(fail(e))); }}>↻ Refresh</button></Heading>
    {error && <Notice error>{error}</Notice>}{message && <Notice>{message}</Notice>}
    <div className="tabs" role="tablist" aria-label="Invoice detail"><button role="tab" aria-selected={tab === "review"} onClick={() => setTab("review")}>Review invoice</button><button role="tab" aria-selected={tab === "audit"} onClick={() => setTab("audit")}>Audit history <span>{events.length}</span></button></div>
    {tab === "audit" ? <section className="panel audit-panel"><div className="panel-title"><div><h2>Every action, accounted for</h2><p className="muted">Append-only history of this invoice.</p></div></div>{events.map(event => <article className="audit-event" key={event.id}><span className="activity-dot"/><div><h3>{title(event.event_type)}</h3><p className="muted">{event.actor} · {time(event.created_at)}</p><pre>{JSON.stringify(event.details, null, 2)}</pre></div></article>)}</section> : <>
      {blockers.length > 0 && <div className="review-banner"><strong>{blockers.length} blocking check{blockers.length === 1 ? "" : "s"} require attention</strong><p>Correct the fields against the source, revalidate, then approve the current revision. Approval cannot waive a blocker.</p></div>}
      <div className="detail-grid"><section className="panel document-panel"><div className="panel-title"><h2>Source document</h2><button disabled={!preview} onClick={async () => { try { download(await binary(token, `/invoices/${id}/file`), invoice.filename); } catch (e) { setError(fail(e)); } }}>↓ Download</button></div>{preview ? invoice.mime_type === "application/pdf" ? <iframe title="Original invoice PDF" src={preview}/> : <img alt="Original uploaded invoice" src={preview}/> : <div className="empty">{previewError || "Loading protected document…"}</div>}<div className="document-meta"><strong>{invoice.filename}</strong><p>{Math.ceil(invoice.byte_size / 1024)} KiB · {invoice.source} · Received {time(invoice.created_at)}</p><details><summary>File fingerprint</summary><code>{invoice.sha256}</code></details></div></section>
      <section className="panel edit-panel"><div className="panel-title"><div><h2>Invoice fields</h2><p className="muted">{readOnly ? "Synthetic snapshot - Read only" : terminal ? "Finalized record · Read only" : "Compare every correction with the source."}</p></div><span className="revision">v{invoice.revision}</span></div>
      {processing && <div className="section-pad"><Notice>{invoice.status === "EXTRACTION_FAILED" ? `Extraction failed: ${invoice.processing_attempts.at(-1)?.error_code || "UNKNOWN"}. Mock mode recognizes only supplied fixtures.` : invoice.status === "EXTRACTING" ? "Extraction is running. Refresh to check the result. An interrupted attempt can be retried after two minutes." : "This document has not been extracted yet."}</Notice><button className="primary" disabled={!!pending} onClick={() => action(invoice.status === "RECEIVED" ? "process" : "retry")}>{pending ? "Processing…" : invoice.status === "RECEIVED" ? "Extract & validate" : "Retry extraction"}</button></div>}
      {draft && <fieldset disabled={terminal || !!pending || processing}><div className="field-grid">{fields.map(key => <label key={key}>{title(key)}<input aria-label={title(key)} value={String(draft[key] ?? "")} onChange={e => field(key, e.target.value)} maxLength={key === "currency" ? 10 : 200} placeholder={key.includes("date") ? "YYYY-MM-DD" : "Not provided"}/></label>)}</div><div className="line-editor"><h3>Line items</h3><div className="table-scroll"><table><thead><tr>{["Description", "Quantity", "Unit price", "Line total", ""].map((label, i) => <th key={i}>{label}</th>)}</tr></thead><tbody>{draft.line_items.map((line, index) => <tr key={index}>{["description", "quantity", "unit_price", "line_total"].map(key => <td key={key}><input aria-label={`Line ${index + 1} ${title(key)}`} value={line[key] ?? ""} onChange={e => setDraft({ ...draft, line_items: draft.line_items.map((row, i) => i === index ? { ...row, [key]: e.target.value || null } : row) })}/></td>)}<td><button aria-label={`Remove line ${index + 1}`} type="button" onClick={() => setDraft({ ...draft, line_items: draft.line_items.filter((_, i) => i !== index) })}>×</button></td></tr>)}</tbody></table></div><button type="button" disabled={draft.line_items.length >= 500} onClick={() => setDraft({ ...draft, line_items: [...draft.line_items, { description: null, quantity: null, unit_price: null, line_total: null }] })}>＋ Add line</button></div><div className="section-pad"><label>Uncertain fields (comma-separated)<input value={draft.uncertain_fields.join(", ")} onChange={e => setDraft({ ...draft, uncertain_fields: e.target.value.split(",").map(s => s.trim()).filter(Boolean) })}/></label><details className="source-evidence"><summary>Source evidence</summary>{Object.entries(draft.evidence).map(([key, value]) => <label key={key}>{title(key)} evidence<input value={value} onChange={e => setDraft({ ...draft, evidence: { ...draft.evidence, [key]: e.target.value } })}/></label>)}<p className="fine">Evidence describes the source. Clear uncertain fields only after verifying them.</p></details></div></fieldset>}
      {!terminal && !processing && <div className="actions-panel"><label>Review / correction notes<textarea value={notes} maxLength={2000} onChange={e => setNotes(e.target.value)} placeholder="What did you verify or change? A reason is required for rejection."/></label><div className="action-row"><button disabled={!!pending || !dirty} onClick={() => action("save")}>{pending === "save" ? "Saving…" : "Save corrections"}</button><button disabled={disabled} onClick={() => action("revalidate")}>{pending === "revalidate" ? "Checking…" : "Revalidate"}</button><button disabled={disabled || !checked || blockers.length > 0 || approved} onClick={() => action("approve")}>{approved ? "Revision approved ✓" : "Approve current revision"}</button><button className="danger" disabled={disabled || !notes.trim()} onClick={() => action("reject")}>Reject invoice</button><button className="primary" disabled={disabled || !checked || blockers.length > 0 || invoice.status !== "READY_TO_POST"} onClick={() => action("post")}>{pending === "post" ? "Posting…" : "Post to ledger →"}</button></div><p className="fine">{dirty ? "Unsaved corrections. Save them before taking another action." : !checked ? "Current revision needs revalidation before approval or posting." : invoice.review_required && !approved ? "Human approval of this revision is required before posting." : "The backend runs fresh checks before committing a ledger entry."}</p></div>}
      {!readOnly && terminal && <div className="section-pad"><Notice>{invoice.status === "POSTED" ? `Posted to ledger ${invoice.ledger_entry_id}.` : "This invoice was rejected. Its history is preserved."}</Notice></div>}
      </section></div>
      <section className="panel rules-panel"><div className="panel-title"><div><h2>Validation checks</h2><p className="muted">{checked ? `Current checks for revision ${invoice.revision}` : "No current validation batch. Revalidate saved corrections."}</p></div><span className="revision">{invoice.validations.filter(rule => rule.passed).length} passed · {blockers.length} blocking</span></div>{[...invoice.validations].sort((a, b) => Number(a.passed) - Number(b.passed)).map((rule, i) => <div className={`rule ${rule.passed ? "passed" : "failed"}`} key={`${rule.rule_code}-${i}`}><span aria-hidden="true">{rule.passed ? "✓" : "!"}</span><div><h3>{title(rule.rule_code)} <small>{rule.passed ? "Passed" : rule.severity}</small></h3><p>{rule.message}</p>{!rule.passed && <div className="rule-values"><div><b>Expected</b><pre>{JSON.stringify(rule.expected, null, 2) || "—"}</pre></div><div><b>Observed</b><pre>{JSON.stringify(rule.observed, null, 2) || "—"}</pre></div></div>}</div></div>)}{!invoice.validations.length && <div className="empty">No current checks to display.</div>}</section>
      <details className="panel raw-extraction"><summary>Original extraction (preserved)</summary><pre>{JSON.stringify(invoice.extracted_data, null, 2)}</pre></details>
    </>}
  </>;
}
