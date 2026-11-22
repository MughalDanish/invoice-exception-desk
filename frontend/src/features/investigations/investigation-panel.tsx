"use client";
import { useState } from "react";
import { FlaskConical, ShieldCheck, RefreshCw, Sparkles } from "lucide-react";
import { useDesk } from "@/components/desk";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { fieldLabel, financial } from "@/lib/presentation";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";
import { QueryError } from "@/components/shared/controls";
import { TechnicalDetails } from "@/components/evidence/technical-details";
import { time, title, type Detail } from "@/lib/api";
import { activeRun, actionLabel, eventMetrics, reportGaps, reportIsCurrent, safeEvidencePath } from "./presentation";
import { useInvestigations, useInvestigation, useInvestigationCommand, useInvestigationEvents, useInvestigationEvidence } from "./queries";
import type { Investigation, InvestigationReport } from "./types";

export function InvestigationPanel({ invoice, dirty }: { invoice: Detail; dirty: boolean }) {
  const { readOnly } = useDesk();
  // Do not mount query-bearing children in the public application.
  if (readOnly) return <div className="p-5 text-sm text-muted-foreground">Financial investigations are available only in the authenticated workspace. This public demo is read-only.</div>;
  return <PrivateInvestigations key={invoice.id} invoice={invoice} dirty={dirty} />;
}
function PrivateInvestigations({ invoice, dirty }: { invoice: Detail; dirty: boolean }) {
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState("");
  const list = useInvestigations(invoice.id, offset);
  const runId = selected || list.data?.items[0]?.run_id || "";
  const detail = useInvestigation(runId, invoice.revision);
  const command = useInvestigationCommand(invoice.id);
  const busy = !!list.data?.items.some((r) => activeRun(r.status));
  const canStart = invoice.status === "NEEDS_REVIEW" && invoice.validated_revision === invoice.revision && !dirty && !busy && !list.error && !!list.data;
  return <section className="space-y-4 p-4 sm:p-5" aria-label="Financial exception investigation">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="space-y-1"><h2 className="flex items-center gap-2 text-sm font-semibold"><Sparkles className="size-4 text-primary" /> Exception investigation</h2><p className="max-w-xl text-xs text-muted-foreground">Advisory evidence and recommendations. Approval and posting remain separate finance actions.</p></div>
      <Button size="sm" disabled={!canStart || command.isPending} loading={command.isPending && command.variables?.action === "start"} onClick={() => command.mutate({ action: "start", revision: invoice.revision, key: crypto.randomUUID() }, { onSuccess: (run) => { setSelected(run.run_id); setOffset(0); } })}>Investigate exceptions</Button>
    </div>
    {!canStart && !busy && <p className="text-xs text-muted-foreground">Start from a saved, currently validated invoice that requires review.</p>}
    {busy && <p role="status" className="text-xs text-muted-foreground">Investigation queued or running. Checking progress automatically.</p>}
    {command.error && <QueryError compact error={command.error} />}
    {list.isPending ? <Skeleton className="h-16 w-full" /> : list.error ? <QueryError compact error={list.error} retry={() => list.refetch()} /> : !list.data?.total ? <p className="rounded-md border border-dashed p-5 text-sm text-muted-foreground">No investigations yet. An investigation gathers evidence without changing this invoice.</p> : <>
      <div className="flex flex-wrap items-center gap-2"><span className="text-xs font-medium">Investigation</span><Select value={runId} onValueChange={setSelected}><SelectTrigger aria-label="Investigation run" className="min-w-0 max-w-full flex-1 text-xs"><SelectValue /></SelectTrigger><SelectContent>{list.data.items.map((run) => <SelectItem key={run.run_id} value={run.run_id}>{time(run.created_at)} &middot; {title(run.status)} &middot; {run.mode === "gemini" ? "Gemini" : "Scripted mock"}</SelectItem>)}</SelectContent></Select><Button variant="ghost" size="icon-sm" aria-label="Refresh investigations" disabled={list.isFetching || detail.isFetching} onClick={() => { void list.refetch(); if (runId) void detail.refetch(); }}><RefreshCw className="size-3.5" /></Button></div>
      {list.data.total > 10 && <div className="flex items-center gap-3 text-xs"><Button variant="outline" size="sm" disabled={!offset} onClick={() => { setOffset(Math.max(0, offset - 10)); setSelected(""); }}>Newer</Button><span>{offset + 1}–{Math.min(offset + 10, list.data.total)} of {list.data.total}</span><Button variant="outline" size="sm" disabled={offset + 10 >= list.data.total} onClick={() => { setOffset(offset + 10); setSelected(""); }}>Older</Button></div>}
      {detail.isPending ? <Skeleton className="h-32 w-full" /> : detail.error ? <QueryError compact error={detail.error} retry={() => detail.refetch()} /> : detail.data && <RunDetails key={runId} run={detail.data} revision={invoice.revision} pending={command.isPending} control={(action) => command.mutate({ action, run: runId })} />}
    </>}
  </section>;
}
function RunDetails({ run, revision, pending, control }: { run: Investigation; revision: number; pending: boolean; control: (action: "cancel" | "retry") => void }) {
  const current = reportIsCurrent(run, revision);
  return <div className="space-y-4">
    <div className="flex flex-wrap items-center gap-2"><Badge variant="outline">{title(run.status)}</Badge><Badge variant="secondary">{run.mode === "gemini" ? <Sparkles className="size-3" /> : <FlaskConical className="size-3" />}{run.mode === "gemini" ? "Live Gemini" : "Scripted mock · offline"}</Badge><span className="text-xs text-muted-foreground">{time(run.created_at)}</span></div>
    {(!run.applicable || run.status === "STALE" || (run.report && !current)) && <div role="status" className="rounded-md border border-amber-300 bg-amber-50 p-3 text-xs text-amber-950">This investigation is stale. Its evidence or invoice version has changed. Start a new investigation before relying on a recommendation.</div>}
    {run.mode === "mock" && <p className="text-xs text-muted-foreground">This is a deterministic development report, not a live AI investigation.</p>}
    {run.error_code && <p role="alert" className="text-sm">Investigation stopped: <span className="font-mono text-xs">{run.error_code}</span>. Review the timeline before retrying.</p>}
    {activeRun(run.status) && <div className="flex flex-wrap items-center gap-3"><p className="text-xs text-muted-foreground">You can leave this page while the worker processes the run.</p><AlertDialog><AlertDialogTrigger asChild><Button variant="outline" size="sm" disabled={pending}>Cancel investigation</Button></AlertDialogTrigger><AlertDialogContent><AlertDialogHeader><AlertDialogTitle>Cancel this investigation?</AlertDialogTitle><AlertDialogDescription>This stops advisory investigation work. The invoice and financial workflows are unchanged. Only the requesting operator can cancel.</AlertDialogDescription></AlertDialogHeader><AlertDialogFooter><AlertDialogCancel>Keep investigating</AlertDialogCancel><AlertDialogAction onClick={() => control("cancel")}>Confirm cancellation</AlertDialogAction></AlertDialogFooter></AlertDialogContent></AlertDialog></div>}
    {run.status === "FAILED" && run.applicable && <div className="space-y-1"><Button variant="outline" size="sm" disabled={pending} onClick={() => control("retry")}>Retry investigation</Button><p className="text-xs text-muted-foreground">Available only to the requesting operator when the server confirms remaining attempts and budget.</p></div>}
    {run.report && current && <Report report={run.report} invoice={run.invoice_id} />}
    <InvestigationTimeline run={run.run_id} active={activeRun(run.status)} />
    <TechnicalDetails label="Investigation technical payload" value={run} />
  </div>;
}
function Report({ report, invoice }: { report: InvestigationReport; invoice: string }) {
  const gaps = reportGaps(report);
  return <div className="space-y-4 text-sm">
    <Separator /><div className="space-y-1"><h3 className="font-semibold">Investigation findings</h3><p className="whitespace-pre-wrap break-words">{report.summary}</p><p className="text-xs text-muted-foreground">Based on invoice revision {report.source_revision}. Cited evidence establishes provenance, not document authenticity.</p></div>
    <ol className="divide-y rounded-md border">{report.findings.map((finding, i) => <li key={`${finding.task_id}-${i}`} className="space-y-1 p-3"><Badge variant="outline">{title(finding.status)}</Badge><p className="whitespace-pre-wrap break-words">{finding.claim}</p><p className="break-all text-xs text-muted-foreground">Evidence: {finding.evidence_ids.join(" · ") || "No evidence reference"}</p></li>)}</ol>
    {!!report.assertions?.length && <details className="rounded-md border p-3"><summary className="cursor-pointer text-xs font-medium">Recorded facts checked against evidence ({report.assertions.length})</summary><div className="mt-2 max-h-80 overflow-auto"><Table><TableHeader><TableRow><TableHead>Recorded field</TableHead><TableHead>Exact value</TableHead><TableHead>Evidence reference</TableHead></TableRow></TableHeader><TableBody>{report.assertions.map((assertion, i) => <TableRow key={i}><TableCell className="max-w-48 break-words text-xs">{fieldLabel(assertion.field_path.split("/").filter(Boolean).at(-1) || assertion.field_path)}</TableCell><TableCell className="max-w-64 whitespace-pre-wrap break-words text-xs tabular-nums">{assertion.value === null ? "Not provided" : typeof assertion.value === "boolean" ? (assertion.value ? "Yes" : "No") : assertion.currency ? financial(assertion.value, assertion.currency) : assertion.value}</TableCell><TableCell className="max-w-48 break-all text-xs text-muted-foreground">{assertion.evidence_id}</TableCell></TableRow>)}</TableBody></Table></div></details>}
    <div className="rounded-md border-l-2 border-primary bg-muted/40 p-3"><h3 className="font-semibold">Recommended next action</h3><p>{actionLabel(report.proposed_action)}</p>{report.resolution_rationale && <p className="mt-1 whitespace-pre-wrap break-words">{report.resolution_rationale}</p>}<p className="mt-2 flex items-center gap-1 text-xs text-muted-foreground"><ShieldCheck className="size-3.5 shrink-0" /> Advisory only. Human authorization is required.</p></div>
    {report.model && <p className="text-xs text-muted-foreground">Model: {report.model}{report.provider_version ? ` · ${report.provider_version}` : ""}</p>}
    {!!gaps.length && <div><h3 className="font-semibold">Unresolved uncertainties and missing evidence</h3><ul className="list-disc space-y-1 pl-5">{gaps.map((gap, i) => <li key={i} className="whitespace-pre-wrap break-words">{gap}</li>)}</ul></div>}
    {!!report.evidence_links?.length && <div className="space-y-2"><h3 className="font-semibold">Supporting sources</h3>{report.evidence_links.map((link) => safeEvidencePath(invoice, link.href) ? <Evidence key={link.citation_id} invoice={invoice} href={link.href} label={link.citation_id} /> : <p key={link.citation_id} className="text-xs text-muted-foreground">Unresolvable evidence reference</p>)}</div>}
    {!!report.limitations?.length && <div className="text-xs text-muted-foreground"><h3 className="font-medium">Limitations</h3><ul className="list-disc space-y-1 pl-5">{report.limitations.map((item, i) => <li key={i}>{item}</li>)}</ul></div>}
  </div>;
}
function Evidence({ invoice, href, label }: { invoice: string; href: string; label: string }) {
  const [open, setOpen] = useState(false);
  return <div className="rounded-md border p-2"><Button variant="ghost" size="sm" className="max-w-full justify-start" aria-expanded={open} onClick={() => setOpen(!open)}><span className="truncate">{open ? "Hide" : "Read"} evidence · {label}</span></Button>{open && <EvidenceBody invoice={invoice} href={href} />}</div>;
}
function EvidenceBody({ invoice, href }: { invoice: string; href: string }) {
  const query = useInvestigationEvidence(invoice, href);
  if (query.isPending) return <Skeleton className="h-16" />;
  if (query.error) return <QueryError compact error={query.error} retry={() => query.refetch()} />;
  if (!query.data) return null;
  if (query.data.invoice_id !== invoice) return <p role="alert" className="text-xs">Evidence scope could not be verified.</p>;
  return <div className="space-y-2 p-2"><p className="text-xs text-muted-foreground">{query.data.kind} · Version {query.data.version} · Untrusted source text</p><blockquote className="whitespace-pre-wrap break-words border-l-2 pl-3 text-sm">{query.data.excerpt}</blockquote><TechnicalDetails label="Source integrity and technical details" value={query.data} /></div>;
}
function InvestigationTimeline({ run, active }: { run: string; active: boolean }) {
  const [after, setAfter] = useState(0);
  const events = useInvestigationEvents(run, after, active);
  return <details className="rounded-md border p-3"><summary className="cursor-pointer text-xs font-medium">Investigation timeline</summary>{events.error ? <QueryError compact error={events.error} retry={() => events.refetch()} /> : events.isPending ? <Skeleton className="mt-2 h-12" /> : <><ol className="mt-3 space-y-2">{events.data?.items.map((event) => <li key={event.seq} className="flex flex-wrap justify-between gap-2 text-xs"><span>{event.seq}. {title(event.event_type)}{eventMetrics(event.details) && <span className="mt-0.5 block break-words text-muted-foreground">{eventMetrics(event.details)}</span>}</span><time className="text-muted-foreground">{time(event.created_at)}</time></li>)}</ol>{!events.data?.items.length && <p className="mt-2 text-xs text-muted-foreground">No additional events recorded.</p>}<div className="mt-3 flex gap-2">{after > 0 && <Button variant="ghost" size="sm" onClick={() => setAfter(0)}>First events</Button>}{events.data?.items.length === 50 && <Button variant="outline" size="sm" onClick={() => setAfter(events.data!.next_after_seq)}>Next events</Button>}</div></>}</details>;
}
