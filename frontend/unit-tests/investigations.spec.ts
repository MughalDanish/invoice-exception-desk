import { test, expect } from "@playwright/test";
import { activeRun, actionLabel, eventMetrics, investigationKeys, reportGaps, reportIsCurrent, safeEvidencePath } from "../src/features/investigations/presentation";
import type { Investigation } from "../src/features/investigations/types";
const id = "00000000-0000-4000-8000-000000000001";
const source = "00000000-0000-4000-8000-000000000002";
const path = `/api/v1/invoices/${id}/evidence/${source}/versions/2`;
test("evidence navigation permits only the exact invoice and versioned authenticated API", () => {
  expect(safeEvidencePath(id, path)).toBe(path.slice(7));
  for (const unsafe of ["javascript:alert(1)", `https://evil.test${path}`, `//evil.test${path}`, path + "?token=secret", path + "#x", path.replace("/2", "/0"), path.replace(`/invoices/${id}/`, `/invoices/${source}/`), path.replace("/versions/2", "/versions/../2")]) expect(safeEvidencePath(id, unsafe)).toBeNull();
  expect(safeEvidencePath(".*", path)).toBeNull();
});
test("a report requires completed, applicable and matching source revision", () => {
  const run = { status: "COMPLETED", applicable: true, report: { source_revision: 3 } } as Investigation;
  expect(reportIsCurrent(run, 3)).toBe(true);
  expect(reportIsCurrent(run, 4)).toBe(false);
  expect(reportIsCurrent({ ...run, applicable: false }, 3)).toBe(false);
  for (const status of ["STALE", "RUNNING", "FAILED", "CANCELLED", "QUEUED"] as const) expect(reportIsCurrent({ ...run, status }, 3)).toBe(false);
});
test("only active statuses poll and keys isolate invoice, run and timeline pages", () => {
  expect(activeRun("QUEUED")).toBe(true); expect(activeRun("RUNNING")).toBe(true);
  for (const status of [undefined, "COMPLETED", "FAILED", "CANCELLED", "STALE", "UNKNOWN"]) expect(activeRun(status)).toBe(false);
  expect(investigationKeys.list(id, 0)).not.toEqual(investigationKeys.list(id, 10));
  expect(investigationKeys.detail(id)).not.toEqual(investigationKeys.detail(source));
  expect(investigationKeys.events(id, 0)).not.toEqual(investigationKeys.events(id, 50));
});
test("unknown recommended actions never turn into financial instructions", () => {
  expect(actionLabel("POST_TO_LEDGER")).toBe("Review the investigation with finance");
  expect(actionLabel("REQUEST_EVIDENCE")).toBe("Request supporting evidence");
  expect(reportGaps({ missing_evidence: ["Original PO"], uncertainties: ["Original PO", "Supplier identity"] } as Investigation["report"] & {})).toEqual(["Original PO", "Supplier identity"]);
});
test("timeline metrics use only known typed telemetry and never prompt data", () => {
  expect(eventMetrics({ tool: "search_evidence", latency_ms: 123, usage: { total_tokens: 50 }, cache_hit: true, prompt: "sensitive source" })).toBe("search_evidence · 123 ms · 50 tokens · Cached tool result");
  expect(eventMetrics({ latency_ms: NaN, usage: { total_tokens: "secret" }, content: "private" })).toBe("");
});
