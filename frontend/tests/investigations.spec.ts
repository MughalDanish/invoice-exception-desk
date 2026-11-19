import { test, expect } from "@playwright/test";
import path from "node:path";

test("operator queues and cancels advisory investigation without financial changes", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Username", { exact: true }).fill("browser-operator");
  await page.getByLabel("Password", { exact: true }).fill("browser-test-password-only");
  await page.getByRole("button", { name: "Open workspace" }).click();
  await expect(page.getByRole("heading", { name: "Overview", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Upload invoice", exact: true }).click();
  await page.getByLabel("Invoice file").setInputFiles(path.resolve(process.cwd(), "../fixtures/invoices/wrong-tax.pdf"));
  const uploaded = page.waitForResponse((response) => response.url().endsWith("/invoices/upload") && response.request().method() === "POST");
  await page.getByRole("button", { name: "Upload & validate", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  const id = (await (await uploaded).json()).invoice_id;
  await page.goto(`/invoices/detail/?id=${id}`);
  await expect(page.getByRole("heading", { name: "Invoice information", exact: true })).toBeVisible();
  const before = await (await page.request.get(`http://localhost:8001/api/v1/invoices/${id}`)).json();
  await page.getByRole("tab", { name: "Investigation", exact: true }).click();
  await page.getByRole("button", { name: "Investigate exceptions", exact: true }).click();
  await expect(page.getByText("Scripted mock · offline", { exact: true })).toBeVisible();
  await expect(page.getByText("Queued", { exact: true })).toBeVisible();
  await page.reload();
  await page.getByRole("tab", { name: "Investigation", exact: true }).click();
  await page.getByRole("button", { name: "Cancel investigation", exact: true }).click();
  await page.getByRole("button", { name: "Confirm cancellation", exact: true }).click();
  await expect(page.getByText("Cancelled", { exact: true })).toBeVisible();
  await page.getByText("Investigation timeline", { exact: true }).click();
  await expect(page.getByText(/Cancelled/).last()).toBeVisible();
  const after = await (await page.request.get(`http://localhost:8001/api/v1/invoices/${id}`)).json();
  expect(after).toEqual(before);
  for (const width of [1440, 1024, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.evaluate(() => { (document.activeElement as HTMLElement | null)?.blur(); window.scrollTo(0, 0); });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    if (width === 390) expect(await page.getByRole("tab", { name: "Investigation", exact: true }).evaluate((tab) => { const box = tab.getBoundingClientRect(); return box.left >= 0 && box.right <= innerWidth; })).toBe(true);
    await page.screenshot({ path: `../storage/day-14-investigation-${width}.png`, fullPage: true });
  }
  // Presentation fixture only: verify untrusted model/source strings are never HTML.
  const runs = await (await page.request.get(`http://localhost:8001/api/v1/invoices/${id}/investigations`)).json();
  const run = runs.items[0];
  const source = "00000000-0000-4000-8000-000000000099";
  const href = `/api/v1/invoices/${id}/evidence/${source}/versions/1`;
  const hostile = '<img src=x onerror="window.__unsafeEvidence=true">';
  await page.route(`**/api/v1/investigations/${run.run_id}`, (route) => route.fulfill({ json: { ...run, status: "COMPLETED", applicable: true, mode: "gemini", report: {
    summary: hostile, findings: [{ task_id: "synthetic", claim: "Synthetic missing purchase order", evidence_ids: ["synthetic-source"], status: "INSUFFICIENT" }],
    source_revision: before.revision, mode: "gemini", advisory_only: true, proposed_action: "REQUEST_EVIDENCE",
    missing_evidence: ["Purchase order"], uncertainties: ["Supplier explanation unavailable"], limitations: ["Synthetic browser fixture"],
    evidence_links: [{ citation_id: "synthetic-source", href }, { citation_id: "unsafe-source", href: "javascript:alert(1)" }],
  } } }));
  await page.route(`**${href}`, (route) => route.fulfill({ json: { source_id: source, invoice_id: id, version: 1, kind: "EMAIL", excerpt: hostile, content_sha256: "0".repeat(64) } }));
  await page.getByRole("button", { name: "Refresh investigations", exact: true }).click();
  await expect(page.getByText("Live Gemini", { exact: true })).toBeVisible();
  await expect(page.getByText(hostile, { exact: true })).toBeVisible();
  await expect(page.getByText("Unresolvable evidence reference", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Read evidence · synthetic-source", exact: true }).click();
  await expect(page.locator("blockquote")).toHaveText(hostile);
  expect(await page.evaluate(() => "__unsafeEvidence" in window)).toBe(false);
  await expect(page.locator('img[src="x"]')).toHaveCount(0);
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.evaluate(() => { (document.activeElement as HTMLElement | null)?.blur(); window.scrollTo(0, 0); });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: `../storage/day-14-report-fixture-${width}.png`, fullPage: true });
  }
});
