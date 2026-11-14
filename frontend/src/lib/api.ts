function apiBase() {
  const url = new URL(
    process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000",
  );
  // Cookie SameSite is host-based, so localhost/127.0.0.1 must agree locally.
  const local = ["localhost", "127.0.0.1", "[::1]"];
  if (
    typeof window !== "undefined" &&
    local.includes(url.hostname) &&
    local.includes(window.location.hostname)
  )
    url.hostname = window.location.hostname;
  return url.toString().replace(/\/$/, "");
}
export const API = apiBase();
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}
let csrf: string | null = null;
let csrfFlight: Promise<string> | null = null;
let refreshFlight: Promise<void> | null = null;
let accessVersion = 0;
let transitioning = false;

async function errorFrom(response: Response) {
  const data = await response.json().catch(() => ({}));
  return new ApiError(
    response.status,
    data.error?.code || "REQUEST_FAILED",
    data.error?.message || `Request failed (${response.status})`,
  );
}
async function raw(path: string, init: RequestInit = {}) {
  return fetch(`${API}/api/v1${path}`, {
    ...init,
    credentials: "include",
    cache: "no-store",
  });
}
async function csrfToken(): Promise<string> {
  if (csrf) return csrf;
  if (!csrfFlight)
    csrfFlight = (async () => {
      const response = await raw("/auth/csrf", {
        signal: AbortSignal.timeout(20000),
      });
      if (!response.ok) throw await errorFrom(response);
      const data = await response.json();
      if (typeof data.csrf_token !== "string")
        throw new ApiError(
          500,
          "INVALID_RESPONSE",
          "Unable to prepare a secure request",
        );
      csrf = data.csrf_token;
      return csrf!;
    })().finally(() => {
      csrfFlight = null;
    });
  return csrfFlight;
}
const renewable = (error: ApiError) =>
  error.status === 401 &&
  ["ACCESS_EXPIRED", "ACCESS_REQUIRED"].includes(error.code);
async function refreshInsideLock() {
  // Another tab may already have renewed the shared cookies while we waited.
  const existing = await raw("/auth/me", {
    signal: AbortSignal.timeout(20000),
  });
  if (existing.ok) {
    accessVersion++;
    return;
  }
  const error = await errorFrom(existing);
  if (!renewable(error)) throw error;
  const response = await raw("/auth/refresh", {
    method: "POST",
    headers: { "X-CSRF-Token": await csrfToken() },
    signal: AbortSignal.timeout(20000),
  });
  if (!response.ok) {
    csrf = null;
    throw await errorFrom(response);
  }
  const data = await response.json();
  csrf = data.csrf_token;
  accessVersion++;
}
async function browserAuthLock<T>(operation: () => Promise<T>): Promise<T> {
  if (typeof navigator !== "undefined" && navigator.locks)
    return await navigator.locks.request("invoice-desk-auth", operation);
  return operation();
}
async function refreshSession() {
  if (transitioning)
    throw new DOMException("Authentication is changing", "AbortError");
  if (!refreshFlight)
    refreshFlight = browserAuthLock(refreshInsideLock).finally(() => {
      refreshFlight = null;
    });
  return refreshFlight;
}
function cancellable<T>(promise: Promise<T>, signal: AbortSignal): Promise<T> {
  if (signal.aborted) return Promise.reject(signal.reason);
  return new Promise((resolve, reject) => {
    const abort = () => reject(signal.reason);
    signal.addEventListener("abort", abort, { once: true });
    promise
      .then(resolve, reject)
      .finally(() => signal.removeEventListener("abort", abort));
  });
}
async function authenticatedFetch(path: string, init: RequestInit = {}) {
  const method = (init.method || "GET").toUpperCase();
  const unsafe = !["GET", "HEAD", "OPTIONS"].includes(method);
  const timeout = AbortSignal.timeout(path.endsWith("/process") ? 240000 : unsafe ? 90000 : 20000);
  const signal = init.signal
    ? AbortSignal.any([init.signal, timeout])
    : timeout;
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  if (unsafe)
    headers.set("X-CSRF-Token", await cancellable(csrfToken(), signal));
  const start = accessVersion;
  let response = await raw(path, { ...init, headers, signal });
  if (response.ok) return response;
  const error = await errorFrom(response);
  const replayable =
    !init.body ||
    typeof init.body === "string" ||
    init.body instanceof FormData ||
    init.body instanceof Blob ||
    init.body instanceof URLSearchParams;
  // These codes are emitted exclusively before a protected business handler runs.
  if (
    renewable(error) &&
    replayable &&
    (!path.startsWith("/auth/") || path === "/auth/me")
  ) {
    if (start === accessVersion) await cancellable(refreshSession(), signal);
    if (unsafe)
      headers.set("X-CSRF-Token", await cancellable(csrfToken(), signal));
    response = await raw(path, { ...init, headers, signal });
    if (response.ok) return response;
    throw await errorFrom(response);
  }
  if (error.code === "CSRF_REJECTED") csrf = null;
  throw error;
}
export async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await authenticatedFetch(path, init);
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
export async function binary(
  path: string,
  signal?: AbortSignal,
): Promise<Blob> {
  return (await authenticatedFetch(path, { signal })).blob();
}
export function acceptAuthentication(csrfToken: string) {
  csrf = csrfToken;
  accessVersion++;
}
export async function authenticationTransition<T>(
  operation: () => Promise<T>,
): Promise<T> {
  transitioning = true;
  try {
    if (refreshFlight) await refreshFlight.catch(() => undefined);
    return await browserAuthLock(operation);
  } finally {
    transitioning = false;
  }
}
export async function logoutAuthentication() {
  await authenticationTransition(() =>
    request<void>("/auth/logout", { method: "POST" }),
  );
  csrf = null;
  accessVersion++;
}
export function forgetAuthentication() {
  csrf = null;
  accessVersion++;
}

export function download(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob),
    a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export const statuses = [
  "RECEIVED",
  "EXTRACTING",
  "READY_TO_POST",
  "NEEDS_REVIEW",
  "POSTED",
  "REJECTED",
  "EXTRACTION_FAILED",
];
export const title = (s: string) =>
  s
    .toLowerCase()
    .replaceAll("_", " ")
    .replace(/^./, (c) => c.toUpperCase());
export const time = (s: string) =>
  new Date(s).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
// Keep monetary strings exactly as supplied by the backend; never round using JS floats.
export const money = (amount?: string | null, currency?: string | null) =>
  amount == null ? "â€”" : `${currency || ""} ${amount}`.trim();
export type Payload = {
  vendor_name: string | null;
  vendor_tax_id: string | null;
  invoice_number: string | null;
  invoice_date: string | null;
  due_date: string | null;
  currency: string | null;
  subtotal: string | null;
  tax_rate: string | null;
  tax_amount: string | null;
  total: string | null;
  line_items: Record<string, string | null>[];
  evidence: Record<string, string>;
  uncertain_fields: string[];
};
export type Invoice = {
  id: string;
  filename: string;
  source: string;
  mime_type: string;
  byte_size: number;
  sha256: string;
  status: string;
  revision: number;
  review_required: boolean;
  validated_revision: number | null;
  current_data: Payload | null;
  created_at: string;
  updated_at: string;
  issue_codes: string[];
};
export type Rule = {
  rule_code: string;
  severity: string;
  passed: boolean;
  message: string;
  expected: unknown;
  observed: unknown;
};
export type Detail = Invoice & {
  extracted_data: Payload | null;
  validations: Rule[];
  reviews: {
    id: string;
    revision: number;
    reviewer: string;
    decision: string;
    notes: string;
    created_at: string;
  }[];
  processing_attempts: {
    ordinal: number;
    status: string;
    error_code: string | null;
  }[];
  ledger_entry_id: string | null;
};
export type Page<T> = {
  items: T[];
  total: number;
  page: number;
  limit: number;
};
export type Event = {
  id: string;
  actor: string;
  event_type: string;
  created_at: string;
  invoice_id?: string | null;
  details?: Record<string, unknown>;
};
export type Stats = {
  total_invoices: number;
  by_status: Record<string, number>;
  duplicate_invoices: number;
  posted_totals_by_currency: Record<string, string>;
  flagged_totals_by_currency: Record<string, string>;
  recent_activity: Event[];
};
export type Vendor = {
  id: string;
  display_name: string;
  expected_currency: string | null;
  baseline_amount_limit: string | null;
  is_approved: boolean;
};
export type Ledger = {
  id: string;
  invoice_id: string;
  vendor_name: string;
  invoice_number: string;
  currency: string;
  total: string;
  posted_at: string;
  posted_by: string;
};
