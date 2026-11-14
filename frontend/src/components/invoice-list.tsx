"use client";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { binary, download, money, request, statuses, time, title, type Invoice, type Page, type Stats } from "@/lib/api";
import { Badge, Heading, Notice, Pager, useDesk } from "./desk";

export function InvoiceTable({ items }: { items: Invoice[] }) {
  return <div className="table-scroll"><table><thead><tr><th>Supplier / Invoice</th><th>Invoice date</th><th className="numeric">Amount</th><th>Status</th><th>Issues</th><th>Received</th><th><span className="sr-only">Action</span></th></tr></thead><tbody>{items.map(row => <tr key={row.id}><td><strong>{row.current_data?.vendor_name || "Awaiting extraction"}</strong><span className="cell-secondary">{row.current_data?.invoice_number || row.filename}</span></td><td>{row.current_data?.invoice_date || "—"}</td><td className="numeric amount">{money(row.current_data?.total, row.current_data?.currency)}</td><td><Badge status={row.status}/></td><td><span title={row.issue_codes.join(", ")} className={row.issue_codes.length ? "issue-count" : "muted"}>{row.issue_codes.length ? `${row.issue_codes.length} flagged` : "—"}</span></td><td className="cell-time">{time(row.created_at)}</td><td><Link className="review-link" href={`/invoices/detail/?id=${row.id}`}>{["POSTED", "REJECTED"].includes(row.status) ? "View" : "Review"} <span aria-hidden="true">↗</span></Link></td></tr>)}</tbody></table>{items.length === 0 && <div className="empty"><span aria-hidden="true">▤</span><h3>No invoices here</h3><p>Upload a synthetic fixture or adjust your filters to get started.</p></div>}</div>;
}
export function InvoiceList({ mode = "all" }: { mode?: "all" | "overview" | "exceptions" }) {
  const { token, readOnly, fail } = useDesk(); const [data, setData] = useState<Page<Invoice> | null>(null);
  const [stats, setStats] = useState<Stats | null>(null); const [status, setStatus] = useState("");
  const [search, setSearch] = useState(""); const [query, setQuery] = useState(""); const [issue, setIssue] = useState(""); const [page, setPage] = useState(1);
  const [error, setError] = useState(""); const [message, setMessage] = useState(""); const [loading, setLoading] = useState(true); const [pending, setPending] = useState("");
  const [uploadOpen, setUploadOpen] = useState(false); const input = useRef<HTMLInputElement>(null);
  useEffect(() => { const timer = setTimeout(() => { setQuery(search); setPage(1); }, 300); return () => clearTimeout(timer); }, [search]);
  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true); setError("");
    try {
      const params = new URLSearchParams({ page: String(page), limit: "20", search: query });
      if (mode === "exceptions") params.set("status", "NEEDS_REVIEW"); else if (status) params.set("status", status);
      if (issue) params.set("issue", issue);
      const [rows, summary] = await Promise.all([request<Page<Invoice>>(token, `/invoices?${params}`, { signal }), request<Stats>(token, "/stats", { signal })]);
      setData(rows); setStats(summary);
    } catch (e) { if (!(e instanceof DOMException && e.name === "AbortError")) setError(fail(e)); }
    finally { if (!signal?.aborted) setLoading(false); }
  // fail only reads the current session. The token controls session changes.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, mode, page, query, status, issue]);
  useEffect(() => { const controller = new AbortController(); void load(controller.signal); return () => controller.abort(); }, [load]);
  async function exportCsv() { setPending("export"); setError(""); try { download(await binary(token, "/ledger/export.csv"), "invoice-ledger.csv"); } catch (e) { setError(fail(e)); } finally { setPending(""); } }
  async function upload(e: FormEvent) {
    e.preventDefault(); const file = input.current?.files?.[0]; if (!file) return;
    if (file.size > 8388608) { setError("Choose a PDF, JPG or PNG of 8 MiB or less."); return; }
    setPending("upload"); setError(""); setMessage("");
    try {
      const body = new FormData(); body.set("file", file);
      const uploaded = await request<{ invoice_id: string; duplicate: boolean; status: string }>(token, "/invoices/upload", { method: "POST", body });
      let result = uploaded;
      if (["RECEIVED", "EXTRACTING"].includes(uploaded.status)) result = { ...uploaded, ...await request<{ status: string }>(token, `/invoices/${uploaded.invoice_id}/process`, { method: "POST" }) };
      setMessage(`${uploaded.duplicate ? "Existing invoice returned" : "Invoice uploaded"}: ${title(result.status)}. Open the invoice to review the result.`);
      setUploadOpen(false); await load();
    } catch (e) { await load(); setError(fail(e)); }
    finally { setPending(""); }
  }
  const overview = mode === "overview";
  return <><Heading eyebrow="ACCOUNTS PAYABLE" title={overview ? "Your invoice desk" : mode === "exceptions" ? "Exception queue" : "All invoices"} subtitle={overview ? "Catch invoice mistakes before they reach your ledger." : mode === "exceptions" ? "Resolve the exceptions. Keep every decision traceable." : "Every document, from first receipt to final decision."}>{!readOnly && <><button onClick={exportCsv} disabled={!!pending}>{pending === "export" ? "Exporting…" : "↓ Export ledger"}</button><button className="primary" onClick={() => setUploadOpen(!uploadOpen)} disabled={!!pending}>＋ Upload invoice</button></>}</Heading>
    {error && <Notice error>{error}</Notice>}{message && <Notice>{message}</Notice>}
    {!readOnly && uploadOpen && <form className="panel upload-panel" onSubmit={upload}><div><h2>Upload a synthetic invoice</h2><p className="muted">PDF, JPG or PNG · Up to 8 MiB. In mock mode, use the supplied fixtures.</p></div><label className="file-label">Invoice file<input ref={input} type="file" accept=".pdf,.jpg,.jpeg,.png" required/></label><button className="primary" disabled={!!pending}>{pending === "upload" ? "Uploading and validating…" : "Upload & validate"}</button><button type="button" disabled={!!pending} onClick={() => setUploadOpen(false)}>Cancel</button></form>}
    {overview && stats && <><section className="kpis" aria-label="Invoice statistics">{[["Total invoices", stats.total_invoices, "All documents received", ""], ["Needs review", stats.by_status.NEEDS_REVIEW, "Waiting for a human decision", "warning"], ["Ready to post", stats.by_status.READY_TO_POST, "Passed current checks", ""], ["Posted", stats.by_status.POSTED, "Recorded in the ledger", "good"], ["Duplicates flagged", stats.duplicate_invoices, "Current duplicate rule failures", ""]].map(([label, value, detail, style]) => <article className={`kpi ${style}`} key={label}><p>{label}</p><strong>{value}</strong><small>{detail}</small></article>)}</section><section className="attention"><div><span className="attention-icon" aria-hidden="true">◇</span><div><h2>{stats.by_status.NEEDS_REVIEW ? `${stats.by_status.NEEDS_REVIEW} invoices need a closer look` : "Your review queue is clear"}</h2><p>Validation holds exceptions before they can reach your ledger.</p></div></div><Link href="/exceptions/">Open exception queue →</Link></section></>}
    <section className="panel"><div className="panel-title"><div><h2>{overview ? "Invoice activity" : "Documents"}</h2><p className="muted">{loading ? "Refreshing records…" : `${data?.total ?? 0} invoices matched`}</p></div><button onClick={() => load()} disabled={loading || !!pending}>↻ Refresh</button></div><div className="filters"><label className="search"><span className="sr-only">Search invoices</span><input aria-label="Search invoices" value={search} onChange={e => setSearch(e.target.value)} placeholder="Search supplier, invoice or filename…"/></label>{mode !== "exceptions" && <label><span className="sr-only">Status</span><select aria-label="Status" value={status} onChange={e => { setStatus(e.target.value); setPage(1); }}><option value="">All statuses</option>{statuses.map(s => <option key={s} value={s}>{title(s)}</option>)}</select></label>}<label><span className="sr-only">Issue type</span><select aria-label="Issue type" value={issue} onChange={e => { setIssue(e.target.value); setPage(1); }}><option value="">All issue types</option>{["TOTAL_MISMATCH", "SUBTOTAL_MISMATCH", "LINE_TOTAL_MISMATCH", "TAX_RATE_MISMATCH", "DUPLICATE_INVOICE", "UNAPPROVED_VENDOR", "MISSING_REQUIRED_FIELD", "INVALID_DATE", "INVALID_DATE_RANGE", "CURRENCY_MISMATCH", "AMOUNT_OUTLIER", "UNCERTAIN_EXTRACTION"].map(code => <option key={code} value={code}>{title(code)}</option>)}</select></label></div>{!data && loading ? <div className="empty" role="status">Loading invoices…</div> : <InvoiceTable items={data?.items || []}/>}<Pager page={page} total={data?.total || 0} onChange={setPage}/></section>
    {overview && stats && <div className="bottom-grid"><section className="panel"><div className="panel-title"><h2>Recent activity</h2><span className="eyebrow">AUDIT LOG</span></div><div className="activity">{stats.recent_activity.map(event => <div className="activity-row" key={event.id}><span className="activity-dot"/><div>{event.invoice_id ? <Link href={`/invoices/detail/?id=${event.invoice_id}`}>{title(event.event_type)}</Link> : <strong>{title(event.event_type)}</strong>}<small>{event.actor} · {time(event.created_at)}</small></div></div>)}{!stats.recent_activity.length && <p className="muted">Activity will appear when you upload an invoice.</p>}</div></section><section className="panel balances"><p className="eyebrow">LEDGER SNAPSHOT</p><h2>Posted value</h2>{Object.entries(stats.posted_totals_by_currency).map(([code, amount]) => <div className="balance" key={code}><span>{code}</span><strong>{amount}</strong></div>)}{!Object.keys(stats.posted_totals_by_currency).length && <p className="muted">No posted entries yet.</p>}<p className="fine">Totals stay separate by currency. Ledger posting is an explicit operator action.</p><div className="substats"><span>Rejected <b>{stats.by_status.REJECTED}</b></span><span>Extraction failed <b>{stats.by_status.EXTRACTION_FAILED}</b></span></div><Link className="review-link" href="/ledger/">View ledger →</Link></section></div>}
  </>;
}
