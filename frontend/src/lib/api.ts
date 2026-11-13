export const API = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) { super(message); }
}
export async function request<T>(token: string, path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Basic ${token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const res = await fetch(`${API}/api/v1${path}`, { ...init, headers, cache: "no-store" });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(res.status, data.error?.code || "REQUEST_FAILED", data.error?.message || `Request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}
export async function binary(token: string, path: string): Promise<Blob> {
  const res = await fetch(`${API}/api/v1${path}`, { headers: { Authorization: `Basic ${token}` }, cache: "no-store" });
  if (!res.ok) throw new ApiError(res.status, "DOWNLOAD_FAILED", "Unable to download this file. Please try again.");
  return res.blob();
}
export function download(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob), a = document.createElement("a");
  a.href = url; a.download = filename; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export const statuses = ["RECEIVED", "EXTRACTING", "READY_TO_POST", "NEEDS_REVIEW", "POSTED", "REJECTED", "EXTRACTION_FAILED"];
export const title = (s: string) => s.toLowerCase().replaceAll("_", " ").replace(/^./, c => c.toUpperCase());
export const time = (s: string) => new Date(s).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
// Keep monetary strings exactly as supplied by the backend; never round using JS floats.
export const money = (amount?: string | null, currency?: string | null) => amount == null ? "—" : `${currency || ""} ${amount}`.trim();
export type Payload = { vendor_name: string | null; vendor_tax_id: string | null; invoice_number: string | null; invoice_date: string | null; due_date: string | null; currency: string | null; subtotal: string | null; tax_rate: string | null; tax_amount: string | null; total: string | null; line_items: Record<string, string | null>[]; evidence: Record<string, string>; uncertain_fields: string[] };
export type Invoice = { id: string; filename: string; source: string; mime_type: string; byte_size: number; sha256: string; status: string; revision: number; review_required: boolean; validated_revision: number | null; current_data: Payload | null; created_at: string; updated_at: string; issue_codes: string[] };
export type Rule = { rule_code: string; severity: string; passed: boolean; message: string; expected: unknown; observed: unknown };
export type Detail = Invoice & { extracted_data: Payload | null; validations: Rule[]; reviews: { id: string; revision: number; reviewer: string; decision: string; notes: string; created_at: string }[]; processing_attempts: { ordinal: number; status: string; error_code: string | null }[]; ledger_entry_id: string | null };
export type Page<T> = { items: T[]; total: number; page: number; limit: number };
export type Event = { id: string; actor: string; event_type: string; created_at: string; invoice_id?: string | null; details?: Record<string, unknown> };
export type Stats = { total_invoices: number; by_status: Record<string, number>; duplicate_invoices: number; posted_totals_by_currency: Record<string, string>; flagged_totals_by_currency: Record<string, string>; recent_activity: Event[] };
export type Vendor = { id: string; display_name: string; expected_currency: string | null; baseline_amount_limit: string | null; is_approved: boolean };
export type Ledger = { id: string; invoice_id: string; vendor_name: string; invoice_number: string; currency: string; total: string; posted_at: string; posted_by: string };
