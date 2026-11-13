import { test, expect, type Page } from "@playwright/test";
import path from "node:path";
import { readFileSync } from "node:fs";
const fixture = (name: string) => path.resolve(process.cwd(), "../fixtures/invoices", name);
async function login(page: Page) {
  await page.goto("/");
  await page.getByLabel("Username", { exact: true }).fill("browser-operator");
  await page.getByLabel("Password", { exact: true }).fill("browser-test-password-only");
  await page.getByRole("button", { name: "Open workspace" }).click();
  await expect(page.getByRole("heading", { name: "Your invoice desk" })).toBeVisible();
}
async function upload(page: Page, name: string) {
  await page.getByRole("button", { name: "Upload invoice", exact: false }).click();
  await page.getByLabel("Invoice file").setInputFiles(fixture(name));
  await page.getByRole("button", { name: "Upload & validate", exact: true }).click();
  await expect(page.getByRole("status").first()).toContainText(/Invoice uploaded|Existing invoice returned/);
}
async function openInvoice(page: Page, name: string) {
  await page.getByRole("row").filter({ hasText: name }).getByRole("link", { name: /Review|View/ }).click();
  await expect(page.getByRole("heading", { name: "Invoice fields", exact: true })).toBeVisible();
}

test("clean, correction, duplicate and supplier review flow through the real API", async ({ page }) => {
  const errors: string[] = []; page.on("pageerror", error => errors.push(error.message));
  await login(page);
  await upload(page, "clean-001.pdf");
  // Fixture invoice numbers are read from the real response rather than assumed.
  const firstRow = page.locator("tbody tr").first();
  await expect(firstRow).toContainText("Ready to post");
  await page.screenshot({ path: "../storage/previews/day-4-overview.png", fullPage: true });
  await firstRow.getByRole("link", { name: "Review" }).click();
  await expect(page.getByRole("heading", { name: "Invoice fields", exact: true })).toBeVisible({ timeout: 30000 });
  await expect(page.getByTitle("Original invoice PDF")).toBeVisible();
  await page.getByRole("button", { name: "Post to ledger" }).click();
  await expect(page.getByRole("status").first()).toContainText("Post completed");
  await expect(page.getByLabel("Total", { exact: true })).toBeDisabled();
  await page.getByRole("link", { name: "All invoices", exact: true }).first().click();
  await upload(page, "wrong-total.pdf");
  await expect(page.locator("tbody tr").first()).toContainText("Needs review");
  await page.locator("tbody tr").first().getByRole("link", { name: "Review" }).click();
  await expect(page.getByRole("button", { name: "Post to ledger" })).toBeDisabled();
  await expect(page.getByRole("heading", { name: /^Total mismatch / })).toBeVisible();
  await page.screenshot({ path: "../storage/previews/day-4-review.png", fullPage: true });
  await page.getByLabel("Total", { exact: true }).fill("2300.00");
  await page.getByLabel("Review / correction notes").fill("Checked source subtotal and tax.");
  await page.getByRole("button", { name: "Save corrections" }).click();
  await expect(page.getByRole("status").first()).toContainText("Corrections saved");
  await page.getByRole("button", { name: "Revalidate", exact: true }).click();
  await expect(page.getByRole("status").first()).toContainText("Revalidate completed");
  await page.getByRole("button", { name: "Approve current revision" }).click();
  await expect(page.getByRole("status").first()).toContainText("Approve completed");
  await page.getByRole("button", { name: "Post to ledger" }).click();
  await expect(page.getByRole("status").first()).toContainText("Post completed");
  await page.getByRole("tab", { name: "Audit history" }).click();
  await expect(page.getByRole("heading", { name: "Invoice corrected" })).toBeVisible();
  await expect(page.getByText('"2300.00"', { exact: false }).first()).toBeVisible();
  await page.getByRole("link", { name: "All invoices", exact: true }).first().click();
  await upload(page, "duplicate-altered.pdf");
  await page.locator("tbody tr").first().getByRole("link", { name: "Review" }).click();
  await expect(page.getByRole("heading", { name: "Duplicate invoice" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve current revision" })).toBeDisabled();
  await page.getByLabel("Review / correction notes").fill("Duplicate of a posted invoice.");
  await page.getByRole("button", { name: "Reject invoice" }).click();
  await expect(page.getByRole("status").first()).toContainText("Reject completed");
  await page.getByRole("link", { name: "Ledger", exact: true }).click();
  await expect(page.locator("tbody tr")).toHaveCount(2);
  const downloaded = page.waitForEvent("download"); await page.getByRole("button", { name: "Export CSV" }).click();
  const csv = await downloaded; expect(csv.suggestedFilename()).toMatch(/\.csv$/);
  await page.getByRole("link", { name: "Suppliers", exact: true }).click();
  await page.getByRole("button", { name: "Register supplier" }).click();
  await page.getByLabel("Supplier name", { exact: true }).fill("Browser Test Supplier");
  await page.getByLabel("Amount limit").fill("5000.00");
  await page.getByRole("button", { name: "Register supplier", exact: true }).last().click();
  await expect(page.getByRole("status").first()).toContainText("Supplier registered");
  await expect(page.getByRole("row").filter({ hasText: "Browser Test Supplier" })).toBeVisible();
  expect(errors).toEqual([]);
});

test("login failure, mobile layout, filters, refresh and credential clearing", async ({ page }) => {
  await page.request.post("http://127.0.0.1:8001/api/v1/invoices/upload", { headers: { Authorization: `Basic ${Buffer.from("browser-operator:browser-test-password-only").toString("base64")}` }, multipart: { file: { name: "clean-005.pdf", mimeType: "application/pdf", buffer: readFileSync(fixture("clean-005.pdf")) } } });
  await page.setViewportSize({ width: 390, height: 844 }); await page.goto("/");
  await page.getByLabel("Username", { exact: true }).fill("wrong"); await page.getByLabel("Password", { exact: true }).fill("wrong"); await page.getByRole("button", { name: "Open workspace" }).click();
  await expect(page.locator(".notice.error")).toContainText("Invalid operator credentials");
  await login(page);
  await expect(page.getByRole("region", { name: "Invoice statistics" })).toBeVisible();
  const overflow = await page.evaluate(() => ({ width: innerWidth, scroll: document.documentElement.scrollWidth, elements: Array.from(document.querySelectorAll("body *")).filter(el => el.getBoundingClientRect().right > innerWidth + 1 && !el.closest(".table-scroll")).slice(0, 12).map(el => [el.tagName, el.className, el.getBoundingClientRect().right]) }));
  expect(overflow.scroll, JSON.stringify(overflow)).toBeLessThanOrEqual(overflow.width);
  await page.screenshot({ path: "../storage/previews/day-4-mobile.png", fullPage: true });
  await page.getByRole("link", { name: "Exception queue", exact: true }).first().click();
  await page.getByLabel("Issue type").selectOption("UNCERTAIN_EXTRACTION");
  await expect(page.getByRole("heading", { name: "No invoices here" })).toBeVisible();
  await page.getByRole("button", { name: "Refresh", exact: false }).click();
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByRole("heading", { name: "Welcome to the desk" })).toBeVisible();
  expect(await page.evaluate(() => [localStorage.length, sessionStorage.length])).toEqual([0, 0]);
});
