import { request } from "@/lib/api";
import type { Citation, EventPage, Investigation, RunPage } from "./types";
import { safeEvidencePath } from "./presentation";
export const investigationApi = {
  list: (id: string, offset: number, signal?: AbortSignal) => request<RunPage>(`/invoices/${id}/investigations?limit=10&offset=${offset}`, { signal }),
  detail: (id: string, signal?: AbortSignal) => request<Investigation>(`/investigations/${id}`, { signal }),
  events: (id: string, after: number, signal?: AbortSignal) => request<EventPage>(`/investigations/${id}/events?after_seq=${after}&limit=50`, { signal }),
  start: (id: string, revision: number, key: string) => request<Investigation>(`/invoices/${id}/investigations`, { method: "POST", body: JSON.stringify({ expected_revision: revision, idempotency_key: key }) }),
  control: (id: string, action: "cancel" | "retry") => request<Investigation>(`/investigations/${id}/${action}`, { method: "POST" }),
  evidence: (invoice: string, href: string, signal?: AbortSignal) => {
    const path = safeEvidencePath(invoice, href);
    if (!path) throw new Error("Evidence reference is outside this invoice");
    return request<Citation>(path, { signal });
  },
};
