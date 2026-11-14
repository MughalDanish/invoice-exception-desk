import { test, expect } from "@playwright/test";
import { QueryObserver } from "@tanstack/react-query";
import {
  createQueryClient,
  queryPolicy,
  shouldRetryRead,
} from "../src/lib/query/client";
import { ApiError } from "../src/lib/api";
import {
  invoiceKeys,
  auditKeys,
  ledgerKeys,
  supplierKeys,
  dashboardKeys,
  exceptionKeys,
} from "../src/lib/query/keys";
import { processingPoll } from "../src/features/invoices/polling";
import { refreshInvoice } from "../src/features/invoices/invalidation";
test("query defaults never retry or queue financial mutations", () => {
  const client = createQueryClient();
  const options = client.getDefaultOptions();
  expect(options.mutations).toMatchObject({
    retry: false,
    networkMode: "always",
    gcTime: 0,
  });
  expect(queryPolicy.staleTime).toBeGreaterThanOrEqual(0);
  expect(queryPolicy.gcTime).toBeGreaterThan(0);
  client.clear();
});
test("read retry excludes authorization, conflicts, aborts and repeated errors", () => {
  for (const code of [400, 401, 403, 404, 409, 422])
    expect(shouldRetryRead(0, new ApiError(code, "TEST", "test"))).toBe(false);
  expect(shouldRetryRead(0, new DOMException("cancelled", "AbortError"))).toBe(
    false,
  );
  expect(shouldRetryRead(0, new DOMException("timeout", "TimeoutError"))).toBe(
    false,
  );
  expect(shouldRetryRead(0, new ApiError(503, "TEST", "test"))).toBe(true);
  expect(shouldRetryRead(1, new Error("network"))).toBe(false);
});
test("identical filtered resources deduplicate and different pages remain isolated", async () => {
  const client = createQueryClient();
  let calls = 0;
  const filters = { page: 1, status: "NEEDS_REVIEW", issue: "TOTAL_MISMATCH" };
  const query = {
    queryKey: invoiceKeys.list(filters),
    queryFn: async () => {
      calls++;
      await new Promise((r) => setTimeout(r, 10));
      return ["held"];
    },
  };
  await Promise.all([
    client.fetchQuery(query),
    client.fetchQuery({ ...query, queryKey: exceptionKeys.list(filters) }),
  ]);
  expect(calls).toBe(1);
  expect(
    client.getQueryData(invoiceKeys.list({ ...filters, page: 2 })),
  ).toBeUndefined();
  client.clear();
});
test("posting invalidates its detail, audit, worklists, overview and ledger only", async () => {
  const client = createQueryClient();
  const touched = [
    invoiceKeys.detail("one"),
    auditKeys.invoice("one"),
    invoiceKeys.list({ page: 1 }),
    dashboardKeys.stats(),
    ledgerKeys.page(1),
  ];
  const unchanged = [
    invoiceKeys.detail("two"),
    invoiceKeys.document("one"),
    supplierKeys.all,
  ];
  for (const key of [...touched, ...unchanged])
    client.setQueryData(key, "cached");
  await refreshInvoice(client, "one", true);
  for (const key of touched)
    expect(client.getQueryState(key)?.isInvalidated).toBe(true);
  for (const key of unchanged)
    expect(client.getQueryState(key)?.isInvalidated).toBe(false);
  client.clear();
});
test("correction does not invalidate unrelated ledger records", async () => {
  const client = createQueryClient();
  client.setQueryData(ledgerKeys.page(1), []);
  await refreshInvoice(client, "one");
  expect(client.getQueryState(ledgerKeys.page(1))?.isInvalidated).toBe(false);
  client.clear();
});
test("session clients do not share protected data and clear cancels requests", async () => {
  const first = createQueryClient();
  const second = createQueryClient();
  first.setQueryData(invoiceKeys.detail("private"), { supplier: "secret" });
  expect(second.getQueryData(invoiceKeys.detail("private"))).toBeUndefined();
  let cancelled = false;
  const observer = new QueryObserver(first, {
    queryKey: ["pending"],
    queryFn: ({ signal }) =>
      new Promise((_resolve, reject) =>
        signal.addEventListener("abort", () => {
          cancelled = true;
          reject(new DOMException("cancelled", "AbortError"));
        }),
      ),
  });
  const unsubscribe = observer.subscribe(() => {});
  await first.cancelQueries();
  first.clear();
  unsubscribe();
  expect(cancelled).toBe(true);
  expect(first.getQueryCache().getAll()).toHaveLength(0);
  second.clear();
});
test("only recent active extraction polls; terminal, missing and invalid states stop", () => {
  const now = Date.parse("2026-11-14T10:00:00Z");
  for (const state of [
    "POSTED",
    "READY_TO_POST",
    "NEEDS_REVIEW",
    "REJECTED",
    "EXTRACTION_FAILED",
    "RECEIVED",
  ])
    expect(processingPoll(state, new Date(now).toISOString(), now)).toBe(false);
  expect(
    processingPoll("EXTRACTING", new Date(now - 10000).toISOString(), now),
  ).toBe(true);
  expect(processingPoll("EXTRACTING", new Date(now - 180000).toISOString(), now)).toBe(true);
  for (const date of [
    undefined,
    "bad",
    new Date(now - 240000).toISOString(),
    new Date(now + 1000).toISOString(),
  ])
    expect(processingPoll("EXTRACTING", date, now)).toBe(false);
});
