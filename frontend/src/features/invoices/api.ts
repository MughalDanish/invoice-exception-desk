import {
  binary,
  request,
  type Detail,
  type Event,
  type Invoice,
  type Page,
  type Payload,
} from "@/lib/api";
import type { InvoiceFilters } from "@/lib/query/keys";
export type InvoiceAction =
  | "save"
  | "revalidate"
  | "approve"
  | "reject"
  | "post"
  | "process"
  | "retry";
export type InvoiceCommand = {
  action: InvoiceAction;
  revision: number;
  changes?: Partial<Payload>;
  notes?: string;
};
export const invoiceApi = {
  list: (filters: InvoiceFilters, signal?: AbortSignal) => {
    const params = new URLSearchParams({
      page: String(filters.page),
      limit: String(filters.limit ?? 20),
      search: filters.search ?? "",
    });
    if (filters.status) params.set("status", filters.status);
    if (filters.issue) params.set("issue", filters.issue);
    return request<Page<Invoice>>(`/invoices?${params}`, { signal });
  },
  detail: (id: string, signal?: AbortSignal) =>
    request<Detail>(`/invoices/${id}`, { signal }),
  audit: (id: string, signal?: AbortSignal) =>
    request<Event[]>(`/invoices/${id}/audit`, { signal }),
  document: (id: string, signal?: AbortSignal) =>
    binary(`/invoices/${id}/file`, signal),
  upload: async (file: File) => {
    const body = new FormData();
    body.set("file", file);
    const uploaded = await request<{
      invoice_id: string;
      status: string;
      duplicate: boolean;
    }>("/invoices/upload", { method: "POST", body });
    if (["RECEIVED", "EXTRACTING"].includes(uploaded.status)) {
      const processed = await request<{ status: string }>(`/invoices/${uploaded.invoice_id}/process`,
        { method: "POST" },
      );
      return { ...uploaded, status: processed.status };
    }
    return uploaded;
  },
  action: (id: string, command: InvoiceCommand) => {
    const { action, revision, changes, notes } = command;
    const base = `/invoices/${id}`;
    if (action === "process" || action === "retry")
      return request<{ status?: string }>(`${base}/process${action === "retry" ? "?retry=true" : ""}`,
        { method: "POST" },
      );
    if (action === "save")
      return request<{ status?: string }>(base, {
        method: "PATCH",
        body: JSON.stringify({ expected_revision: revision, changes, notes }),
      });
    if (action === "approve" || action === "reject")
      return request<{ status?: string }>(`${base}/review`, {
        method: "POST",
        body: JSON.stringify({
          expected_revision: revision,
          decision: action === "approve" ? "APPROVE" : "REJECT",
          notes,
        }),
      });
    return request<{ status?: string }>(`${base}/${action}`, {
      method: "POST",
      body: JSON.stringify({ expected_revision: revision }),
    });
  },
};
