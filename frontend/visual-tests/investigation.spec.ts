import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

test("synthetic investigation presentation fits desktop and mobile without API or model execution", async ({ page }) => {
  const fixture = JSON.parse(readFileSync(path.resolve(process.cwd(), "../fixtures/public-demo.json"), "utf8"));
  const invoice = fixture.invoices.find((row: { filename: string }) => row.filename === "wrong-tax.pdf");
  const runId = "00000000-0000-4000-8000-000000000014";
  const sourceId = "00000000-0000-4000-8000-000000000015";
  const href = `/api/v1/invoices/${invoice.id}/evidence/${sourceId}/versions/1`;
  const run = {
    run_id: runId, invoice_id: invoice.id, status: "COMPLETED", applicable: true,
    mode: "gemini", created_at: "2026-11-19T08:00:00Z", error_code: null,
    report: {
      summary: "Supporting evidence is needed to resolve the recorded tax exception.",
      findings: [{ task_id: "synthetic", claim: "The recorded tax exception remains unresolved by the available supplier correspondence.", evidence_ids: ["synthetic-email"], status: "INSUFFICIENT" }],
      proposed_action: "REQUEST_EVIDENCE", missing_evidence: ["Supplier explanation of the tax calculation"],
      uncertainties: ["Original supporting purchase order has not been verified"],
      limitations: ["Synthetic UI fixture. This is not an actual Gemini investigation."],
      source_revision: invoice.revision, mode: "gemini", advisory_only: true,
      evidence_links: [{ citation_id: "synthetic-email", href }],
      assertions: [{ evidence_id: "synthetic-email", field_path: "/total", value: "12345678901234567890.001200", currency: "USD" }],
    },
  };
  const apiRequests: string[] = [];
  await page.route("**/api/v1/**", async (route) => {
    const endpoint = new URL(route.request().url()).pathname;
    apiRequests.push(endpoint);
    let json: unknown;
    if (endpoint === "/api/v1/config") json = { read_only: false };
    else if (endpoint === "/api/v1/auth/me") json = { id: runId, session_id: sourceId, username: "synthetic-ui-review", role: "OPERATOR" };
    else if (endpoint.endsWith("/audit")) json = [];
    else if (endpoint.endsWith("/file")) return route.fulfill({ contentType: "application/pdf", body: readFileSync(path.resolve(process.cwd(), "../fixtures/invoices/wrong-tax.pdf")) });
    else if (endpoint === `/api/v1/invoices/${invoice.id}`) json = invoice;
    else if (endpoint.endsWith("/investigations")) json = { items: [{ ...run, report: null }], total: 1, offset: 0, limit: 10 };
    else if (endpoint.endsWith("/events")) json = { items: [{ seq: 1, event_type: "COMPLETED", created_at: run.created_at, details: {} }], next_after_seq: 1 };
    else if (endpoint === `/api/v1/investigations/${runId}`) json = run;
    else if (endpoint === href) json = { source_id: sourceId, invoice_id: invoice.id, version: 1, kind: "EMAIL", excerpt: "Supplier correspondence requests finance review; no supporting tax reconciliation was provided.", content_sha256: "0".repeat(64) };
    else return route.fulfill({ status: 404, json: { error: { code: "FIXTURE_ROUTE_MISSING", message: "Unmapped synthetic fixture endpoint" } } });
    return route.fulfill({ json });
  });
  await page.goto(`/invoices/detail/?id=${invoice.id}`);
  await page.getByRole("tab", { name: "Investigation", exact: true }).click();
  await expect(page.getByText(run.report.summary, { exact: true })).toBeVisible();
  await page.getByText(/Recorded facts checked against evidence/).click();
  await expect(page.getByRole("cell", { name: "USD 12,345,678,901,234,567,890.001200", exact: true })).toBeVisible();
  await page.getByText(/Recorded facts checked against evidence/).click();
  await page.getByRole("button", { name: "Read evidence · synthetic-email", exact: true }).click();
  await expect(page.locator("blockquote")).toContainText("no supporting tax reconciliation");
  for (const width of [1440, 1024, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.evaluate(() => { (document.activeElement as HTMLElement | null)?.blur(); window.scrollTo(0, 0); });
    const tab = page.getByRole("tab", { name: "Investigation", exact: true });
    expect(await tab.evaluate((element) => { const box = element.getBoundingClientRect(); return box.left >= 0 && box.right <= innerWidth; })).toBe(true);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: `../storage/day-14-report-fixture-${width}.png`, fullPage: true });
  }
  expect(apiRequests.every((endpoint) => endpoint.startsWith("/api/v1/"))).toBe(true);
});
