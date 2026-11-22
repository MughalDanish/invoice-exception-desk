export type InvestigationStatus = "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED" | "CANCELLED" | "STALE";
export type Citation = {
  source_id: string; version: number; invoice_id: string; supplier_key: string;
  kind: string; content_sha256: string; excerpt: string; start: number; end: number;
};
export type InvestigationReport = {
  summary: string;
  findings: { task_id: string; claim: string; evidence_ids: string[]; status: string }[];
  proposed_action: string; missing_evidence: string[]; limitations: string[];
  source_revision: number; mode: "mock" | "gemini"; advisory_only: true;
  citations?: Citation[]; evidence_links?: { citation_id: string; href: string }[];
  uncertainties?: string[];
  resolution_rationale?: string | null;
  assertions?: { evidence_id: string; field_path: string; value: string | boolean | null; currency?: string | null }[];
  model?: string | null;
  provider_version?: string | null;
};
export type Investigation = {
  run_id: string; invoice_id: string; status: InvestigationStatus; applicable: boolean;
  mode: "mock" | "gemini"; created_at: string; report: InvestigationReport | null;
  error_code: string | null; can_cancel?: boolean; can_retry?: boolean;
};
export type RunPage = { items: Investigation[]; total: number; limit: number; offset: number };
export type RunEvent = { seq: number; event_type: string; created_at: string; details: Record<string, unknown> };
export type EventPage = { items: RunEvent[]; next_after_seq: number };
