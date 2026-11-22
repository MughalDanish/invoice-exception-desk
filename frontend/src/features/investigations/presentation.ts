import type { Investigation, InvestigationReport } from "./types";

export const activeRun = (status?: string) => status === "QUEUED" || status === "RUNNING";
export const investigationKeys = {
  all: ["investigations"] as const,
  list: (invoice: string, offset: number) => ["investigations", "invoice", invoice, offset] as const,
  detail: (run: string) => ["investigations", "run", run] as const,
  events: (run: string, after: number) => ["investigations", "events", run, after] as const,
  evidence: (invoice: string, path: string) => ["investigations", "evidence", invoice, path] as const,
};
export function reportIsCurrent(run: Investigation, revision: number) {
  return run.status === "COMPLETED" && run.applicable && run.report?.source_revision === revision;
}
// A server URL is data, not navigation authority. Permit only this invoice's versioned API route.
export function safeEvidencePath(invoice: string, href: string): string | null {
  const uuid = "[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}";
  if (!new RegExp(`^${uuid}$`).test(invoice)) return null;
  const prefix = `/api/v1/invoices/${invoice}/evidence/`;
  if (!href.startsWith(prefix) || !new RegExp(`^${uuid}/versions/[1-9][0-9]*$`).test(href.slice(prefix.length))) return null;
  return href.slice("/api/v1".length);
}
export function reportGaps(report: InvestigationReport): string[] {
  return [...new Set([...(report.missing_evidence || []), ...(report.uncertainties || [])])];
}
export const actionLabel = (action: string) => ({
  REQUEST_CORRECTED_INVOICE: "Request a corrected invoice", REQUEST_EVIDENCE: "Request supporting evidence",
  REVIEW_DUPLICATE: "Review a possible duplicate", REVIEW_SUPPLIER: "Review supplier authorization",
  REVIEW_POLICY: "Review the applicable policy", NO_RECOMMENDATION: "No recommendation available",
}[action] || "Review the investigation with finance");
export function eventMetrics(details: Record<string, unknown>): string {
  const values: string[] = [];
  if (typeof details.tool === "string") values.push(details.tool);
  if (typeof details.latency_ms === "number" && Number.isFinite(details.latency_ms) && details.latency_ms >= 0) values.push(`${details.latency_ms} ms`);
  const usage = details.usage;
  if (usage && typeof usage === "object" && "total_tokens" in usage && typeof usage.total_tokens === "number" && Number.isFinite(usage.total_tokens) && usage.total_tokens >= 0) values.push(`${usage.total_tokens} tokens`);
  if (details.cache_hit === true) values.push("Cached tool result");
  return values.join(" · ");
}
