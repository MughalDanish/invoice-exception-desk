import { test, expect, type Page } from "@playwright/test";
async function navigate(page: Page, name: string) {
  if (page.viewportSize()!.width < 768)
    await page.getByRole("button", { name: "Toggle navigation" }).click();
  await page.getByRole("link", { name, exact: true }).first().click();
  await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
}
async function technical(page: Page) {
  await page.getByRole("button", { name: "Invoice options" }).click();
  await page.getByRole("menuitem", { name: "Technical details" }).click();
  return JSON.parse(
    await page.getByLabel("Preserved technical JSON").innerText(),
  );
}
test("anonymous synthetic demo is readable, immutable, and useful on mobile", async ({
  page,
}) => {
  const errors: string[] = [];
  const investigationRequests: string[] = [];
  page.on("request", (request) => { if (request.url().includes("/investigations")) investigationRequests.push(request.url()); });
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(
    page.getByText("Read-only synthetic demonstration", { exact: false }),
  ).toBeVisible();
  await expect(page.locator("tbody tr")).toHaveCount(5);
  await expect(
    page.getByRole("button", { name: "Upload invoice" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("textbox", { name: "Password", exact: true }),
  ).toHaveCount(0);
  await navigate(page, "All invoices");
  await expect(page.locator("tbody tr")).toHaveCount(15);
  await page.locator("tbody tr").first().getByRole("button").click();
  await expect(
    page.getByRole("menuitem", { name: "Open invoice" }),
  ).toBeVisible();
  expect(page.url()).not.toContain("detail");
  await page.keyboard.press("Escape");
  await navigate(page, "Exception queue");
  await page.getByRole("combobox", { name: "Issue type" }).click();
  await page
    .getByRole("option", { name: "Invoice total", exact: true })
    .click();
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await page.locator("tbody tr td").nth(1).click();
  await expect(page.getByLabel("Total", { exact: true })).toBeDisabled();
  await expect(page.getByTitle("Original source document")).toBeVisible();
  await page.getByRole("tab", { name: "Investigation", exact: true }).click();
  await expect(page.getByText(/Financial investigations are available only/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Investigate exceptions", exact: true })).toHaveCount(0);
  expect(investigationRequests).toEqual([]);
  await page.getByRole("tab", { name: "Review invoice", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Post to ledger" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Approve revision" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "Invoice total", exact: true }),
  ).toBeVisible();
  const passed = page.locator(
    '.successful-checks [data-slot="accordion-trigger"]',
  );
  await expect(passed).toHaveAttribute("data-state", "closed");
  await passed.click();
  await expect(
    page.getByRole("heading", { name: "Invoice date range", exact: true }),
  ).toBeVisible();
  await passed.click();
  await page
    .getByRole("tab", { name: "Original extraction", exact: true })
    .click();
  const original = page.getByRole("region", {
    name: "Original extraction",
    exact: true,
  });
  await expect(original).toContainText("USD 2,500.00");
  await original.getByRole("button", { name: "View source JSON" }).click();
  const sheet = page.getByRole("dialog");
  const source = JSON.parse(await sheet.locator("pre").innerText());
  expect(source.total).toBe("2500.00");
  expect(source.currency).toBe("USD");
  await page.context().grantPermissions(["clipboard-read", "clipboard-write"]);
  await sheet.getByRole("button", { name: "Copy JSON", exact: true }).click();
  await expect(sheet.getByRole("status")).toHaveText("JSON copied.");
  expect(
    JSON.parse(await page.evaluate(() => navigator.clipboard.readText())),
  ).toEqual(source);
  await page.evaluate(() =>
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: () => Promise.reject(new Error("denied")) },
    }),
  );
  await sheet.getByRole("button", { name: "Copy JSON", exact: true }).click();
  await expect(sheet.getByRole("status")).toContainText(
    "Clipboard unavailable",
  );
  await sheet.getByRole("button", { name: "Select JSON", exact: true }).click();
  expect(
    JSON.parse(
      await page.evaluate(() => window.getSelection()?.toString() || "null"),
    ),
  ).toEqual(source);
  await sheet.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByRole("tab", { name: "Activity history" }).click();
  await expect(
    page.getByRole("heading", { name: "Activity history" }),
  ).toBeVisible();
  await expect(page.locator(".financial-timeline")).toContainText(
    "Invoice extraction started",
  );
  await expect(page.locator(".financial-timeline pre")).toHaveCount(0);
  await page.setViewportSize({ width: 390, height: 844 });
  const sourceBounds = await page.locator(".document-pane").boundingBox();
  const reviewBounds = await page.locator(".review-pane").boundingBox();
  expect(reviewBounds!.y).toBeGreaterThanOrEqual(
    sourceBounds!.y + sourceBounds!.height,
  );
  await page.setViewportSize({ width: 1440, height: 1000 });
  await navigate(page, "Suppliers");
  await expect(
    page.getByRole("button", { name: "Register supplier" }),
  ).toHaveCount(0);
  await navigate(page, "Ledger");
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await expect(page.getByRole("button", { name: "Export CSV" })).toHaveCount(0);
  const denied = await page.request.post(
    "http://127.0.0.1:8002/api/v1/vendors",
    { data: { display_name: "attacker" } },
  );
  expect(denied.status()).toBe(403);
  await page.setViewportSize({ width: 390, height: 844 });
  await navigate(page, "Overview");
  await expect(page.locator("tbody tr")).toHaveCount(5);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await navigate(page, "All invoices");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  expect(errors).toEqual([]);
});
test("missing extraction and unknown untrusted audit evidence remain readable and inert", async ({
  page,
}) => {
  const marker = '<img src=x onerror="window.__unsafeEvidence=true">';
  await page.route("**/api/v1/invoices/*/audit", async (route) => {
    const response = await route.fetch();
    const events = await response.json();
    await route.fulfill({
      response,
      json: [
        ...events,
        {
          id: "browser-only-unknown-event",
          actor: marker,
          created_at: "invalid timestamp",
          event_type: "FUTURE_EVENT",
          details: { notes: marker, extra: { unexpected: null } },
        },
      ],
    });
  });
  await page.goto("/invoices/");
  await page.getByLabel("Search invoices").fill("extraction-failure");
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await page.locator("tbody tr td").nth(1).click();
  await page
    .getByRole("tab", { name: "Original extraction", exact: true })
    .click();
  const original = page.getByRole("region", {
    name: "Original extraction",
    exact: true,
  });
  await expect(original).toContainText("No original extraction was supplied");
  await original.getByRole("button", { name: "View source JSON" }).click();
  expect(
    JSON.parse(await page.getByRole("dialog").locator("pre").innerText()),
  ).toBeNull();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Close", exact: true })
    .click();
  await page.getByRole("tab", { name: "Activity history" }).click();
  const unknown = page
    .locator("article.event-content")
    .filter({
      has: page.getByRole("heading", {
        name: "Recorded activity",
        exact: true,
      }),
    });
  await expect(unknown).toContainText("Time not recorded");
  await expect(unknown).toContainText(marker);
  await expect(unknown.locator("img")).toHaveCount(0);
  const preserved = await technical(page);
  const event = preserved.audit.find(
    (e: { event_type: string }) => e.event_type === "FUTURE_EVENT",
  );
  expect(event.details.notes).toBe(marker);
  expect(
    await page.evaluate(() => Reflect.get(window, "__unsafeEvidence")),
  ).toBeUndefined();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
test("initial, background, offline and error loading states recover", async ({
  page,
}) => {
  let release: (() => void) | undefined;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/api/v1/invoices?**", async (route) => {
    await gate;
    await route.continue();
  });
  await page.goto("/invoices/");
  await expect(
    page.getByRole("status", { name: "Loading records" }),
  ).toBeVisible();
  release!();
  await expect(page.locator("tbody tr")).toHaveCount(15);
  await page.context().setOffline(true);
  await expect(
    page.getByText("You are offline.", { exact: false }),
  ).toBeVisible();
  await page.context().setOffline(false);
  await expect(
    page.getByText("You are offline.", { exact: false }),
  ).toHaveCount(0);
  await page.unroute("**/api/v1/invoices?**");
  let fail: (() => void) | undefined;
  const background = new Promise<void>((resolve) => {
    fail = resolve;
  });
  await page.route("**/api/v1/invoices?**", async (route) => {
    await background;
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: "{}",
    });
  });
  await page.getByLabel("Search invoices").fill("failed request");
  await expect(
    page.getByText(
      "Updating results. Previous records are shown temporarily.",
      { exact: true },
    ),
  ).toBeVisible();
  fail!();
  await expect(page.locator('.query-error[role="alert"]')).toContainText(
    "temporarily unavailable",
  );
  await page.unroute("**/api/v1/invoices?**");
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(
    page.getByRole("heading", { name: "No invoices match" }),
  ).toBeVisible();
  await expect(page.locator('.query-error[role="alert"]')).toHaveCount(0);
});
