export type InvoiceFilters = {
  page: number;
  limit?: number;
  search?: string;
  status?: string;
  issue?: string;
};
export const dashboardKeys = {
  all: ["dashboard"] as const,
  stats: () => ["dashboard", "stats"] as const,
};
export const invoiceKeys = {
  all: ["invoices"] as const,
  lists: () => ["invoices", "list"] as const,
  list: (filters: InvoiceFilters) => ["invoices", "list", filters] as const,
  detail: (id: string) => ["invoices", "detail", id] as const,
  document: (id: string) => ["invoices", "document", id] as const,
};
// Exceptions share the actual filtered invoice resource, so identical requests deduplicate.
export const exceptionKeys = {
  list: (filters: InvoiceFilters) =>
    invoiceKeys.list({ ...filters, status: "NEEDS_REVIEW" }),
};
export const auditKeys = { invoice: (id: string) => ["audit", id] as const };
export const supplierKeys = { all: ["suppliers"] as const };
export const ledgerKeys = {
  all: ["ledger"] as const,
  page: (page: number) => ["ledger", "page", page] as const,
};
