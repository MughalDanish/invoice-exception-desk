import { test, expect, type Page } from "@playwright/test";
import path from "node:path";
import { readFileSync } from "node:fs";
const fixture = (name: string) =>
  path.resolve(process.cwd(), "../fixtures/invoices", name);
async function login(page: Page) {
  await page.goto("/");
  if (page.viewportSize()!.width === 1440)
    await page.screenshot({
      path: "../storage/ui-redesign/login-desktop.png",
      fullPage: true,
    });
  await page.getByLabel("Username", { exact: true }).fill("browser-operator");
  await page
    .getByLabel("Password", { exact: true })
    .fill("browser-test-password-only");
  await page.getByRole("button", { name: "Open workspace" }).click();
  await expect(
    page.getByRole("heading", { name: "Overview", exact: true }),
  ).toBeVisible();
}
async function navigate(page: Page, name: string) {
  if (page.viewportSize()!.width < 768)
    await page.getByRole("button", { name: "Toggle navigation" }).click();
  await page.getByRole("link", { name, exact: true }).first().click();
  await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
}
async function upload(page: Page, name: string) {
  await page
    .getByRole("button", { name: "Upload invoice", exact: true })
    .click();
  await page.getByLabel("Invoice file").setInputFiles(fixture(name));
  await page
    .getByRole("button", { name: "Upload & validate", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(
    page
      .getByText(/Invoice uploaded and checked|Existing invoice returned/)
      .last(),
  ).toBeVisible();
}
async function openFirst(page: Page) {
  await page.locator("tbody tr").first().locator("td").nth(1).click();
  await expect(
    page.getByRole("heading", { name: "Invoice information", exact: true }),
  ).toBeVisible();
}
async function confirm(
  page: Page,
  action: "posting" | "approval" | "rejection",
) {
  await page.getByRole("button", { name: `Confirm ${action}` }).click();
  await expect(page.getByRole("alertdialog")).toHaveCount(0);
}
async function technical(page: Page) {
  await page.getByRole("button", { name: "Invoice options" }).click();
  await page.getByRole("menuitem", { name: "Technical details" }).click();
  return JSON.parse(
    await page.getByLabel("Preserved technical JSON").innerText(),
  );
}
test("clean, correction, duplicate and supplier review flow through the real API", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await login(page);
  await navigate(page, "All invoices");
  await upload(page, "clean-001.pdf");
  await expect(page.locator("tbody tr").first()).toContainText("Ready to post");
  await openFirst(page);
  await expect(page.getByTitle("Original source document")).toBeVisible();
  await page.getByRole("button", { name: "Post to ledger" }).click();
  await confirm(page, "posting");
  await expect(
    page.getByText("Invoice posted to the ledger.", { exact: true }).last(),
  ).toBeVisible();
  await navigate(page, "All invoices");
  await upload(page, "wrong-total.pdf");
  await openFirst(page);
  await expect(
    page.getByRole("heading", { name: "Invoice total", exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: "../storage/ui-redesign/operator-review-desktop.png",
    fullPage: true,
  });
  await expect(
    page.locator('.successful-checks [data-slot="accordion-trigger"]'),
  ).toHaveAttribute("data-state", "closed");
  await page.getByLabel("Total", { exact: true }).fill("2300.00");
  await page
    .getByLabel("Reason / review notes", { exact: true })
    .fill("Checked source subtotal and tax.");
  await page.getByRole("button", { name: "Save corrections" }).click();
  await expect(
    page
      .getByText(
        "Corrections saved. Revalidate this version before approval.",
        { exact: true },
      )
      .last(),
  ).toBeVisible();
  await page.getByRole("button", { name: "Revalidate", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Approve revision", exact: true }),
  ).toBeEnabled();
  await page
    .getByRole("button", { name: "Approve revision", exact: true })
    .click();
  await confirm(page, "approval");
  await expect(
    page.getByRole("region", { name: "Information provenance" }),
  ).toContainText("Approved revision 2");
  await page.getByRole("button", { name: "Post to ledger" }).click();
  await confirm(page, "posting");
  await expect(page.getByLabel("Total", { exact: true })).toBeDisabled();
  await page
    .getByRole("tab", { name: "Original extraction", exact: true })
    .click();
  const original = page.getByRole("region", {
    name: "Original extraction",
    exact: true,
  });
  await expect(original).toContainText("USD 2,500.00");
  await original.locator(".original-comparison summary").click();
  await expect(original.locator(".original-comparison")).toContainText(
    "USD 2,300.00",
  );
  await page.getByRole("tab", { name: "Activity history" }).click();
  const correction = page.locator("article.event-content").filter({
    has: page.getByRole("heading", {
      name: "Invoice corrected",
      exact: true,
    }),
  });
  await expect(correction).toContainText("2,500.00");
  await expect(correction).toContainText("2,300.00");
  await expect(correction).toContainText("Checked source subtotal and tax.");
  await expect(correction.locator("pre")).toHaveCount(0);
  const preserved = await technical(page);
  const recorded = preserved.audit.find(
    (e: { event_type: string }) => e.event_type === "INVOICE_CORRECTED",
  );
  expect(recorded.details.diff.total).toEqual({
    before: "2500.00",
    after: "2300.00",
  });
  expect(recorded.actor).toBe("browser-operator");
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await navigate(page, "All invoices");
  await upload(page, "duplicate-altered.pdf");
  await openFirst(page);
  await expect(
    page.getByRole("heading", { name: "Duplicate invoice identity" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Approve revision" }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Reject", exact: true }).click();
  await page
    .getByLabel("Reason / notes (required)")
    .fill("Duplicate of a posted invoice.");
  await confirm(page, "rejection");
  await navigate(page, "Ledger");
  await expect(page.locator("tbody tr")).toHaveCount(2);
  const downloaded = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export CSV" }).click();
  expect((await downloaded).suggestedFilename()).toMatch(/\.csv$/);
  await navigate(page, "Suppliers");
  await page
    .getByRole("button", { name: "Register supplier", exact: true })
    .click();
  await page
    .getByLabel("Supplier name", { exact: true })
    .fill("Browser Test Supplier");
  await page.getByLabel("Amount limit").fill("5000.00");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Register supplier" })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(
    page.getByRole("row").filter({ hasText: "Browser Test Supplier" }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});
test("login failure, mobile drawer, filters, nested actions and credential clearing", async ({
  page,
}) => {
  const { request: playwrightRequest } = await import("@playwright/test");
  const seed = await playwrightRequest.newContext();
  const challenge = await (
    await seed.get("http://localhost:8001/api/v1/auth/csrf")
  ).json();
  const signed = await (
    await seed.post("http://localhost:8001/api/v1/auth/login", {
      headers: { "X-CSRF-Token": challenge.csrf_token },
      data: {
        username: "browser-operator",
        password: "browser-test-password-only",
      },
    })
  ).json();
  await seed.post("http://localhost:8001/api/v1/invoices/upload", {
    headers: { "X-CSRF-Token": signed.csrf_token },
    multipart: {
      file: {
        name: "clean-005.pdf",
        mimeType: "application/pdf",
        buffer: readFileSync(fixture("clean-005.pdf")),
      },
    },
  });
  await seed.dispose();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  if (page.viewportSize()!.width === 1440)
    await page.screenshot({
      path: "../storage/ui-redesign/login-desktop.png",
      fullPage: true,
    });
  await page.getByLabel("Username", { exact: true }).fill("wrong");
  await page.getByLabel("Password", { exact: true }).fill("wrong");
  await page.getByRole("button", { name: "Open workspace" }).click();
  await expect(page.locator(".login-form [role=alert]")).toContainText(
    "Username or password is incorrect",
  );
  await login(page);
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Overview", exact: true }),
  ).toBeVisible();
  const authCookies = (await page.context().cookies()).filter((c) =>
    c.name.startsWith("ied_"),
  );
  expect(authCookies.length).toBe(3);
  expect(authCookies.every((c) => c.httpOnly)).toBe(true);
  await page.context().clearCookies({ name: "ied_access" });
  await page.reload();
  await expect(
    page.getByRole("region", { name: "Invoice statistics" }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await navigate(page, "All invoices");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  const row = page.locator("tbody tr").first();
  await row.getByRole("button", { name: /Actions for/ }).click();
  await expect(
    page.getByRole("menuitem", { name: "Copy invoice reference" }),
  ).toBeVisible();
  expect(page.url()).not.toContain("detail");
  await page.keyboard.press("Escape");
  await navigate(page, "Exception queue");
  await page.getByRole("combobox", { name: "Issue type" }).click();
  await page
    .getByRole("option", { name: "Extraction evidence", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "No invoices match" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Toggle navigation" }).click();
  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await expect(
    page.getByRole("heading", { name: "Sign in to your workspace" }),
  ).toBeVisible();
  expect(
    await page.evaluate(() => [localStorage.length, sessionStorage.length]),
  ).toEqual([0, 0]);
  await login(page);
  await navigate(page, "All invoices");
  await expect(
    page.getByRole("row").filter({ hasText: "clean-005.pdf" }),
  ).toBeVisible();
});
