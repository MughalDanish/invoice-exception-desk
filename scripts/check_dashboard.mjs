// Read-only check of the built local dashboard. Never prints operator credentials.
import { chromium } from "../frontend/node_modules/playwright/index.mjs";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
const root = fileURLToPath(new URL("../", import.meta.url));
const env = Object.fromEntries(readFileSync(`${root}/.env`, "utf8").split(/\r?\n/).filter(line => /^[A-Z_]+=/.test(line)).map(line => { const i = line.indexOf("="); return [line.slice(0, i), line.slice(i + 1).replace(/^(['"])(.*)\1$/, "$2")]; }));
const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = []; page.on("pageerror", e => errors.push(e.message));
  await page.goto(process.env.DASHBOARD_URL || "http://localhost:3000");
  await page.getByLabel("Username", { exact: true }).fill(env.DEMO_BASIC_USER);
  await page.getByLabel("Password", { exact: true }).fill(env.DEMO_BASIC_PASSWORD);
  await page.getByRole("button", { name: "Open workspace" }).click();
  await page.getByRole("region", { name: "Invoice statistics" }).waitFor();
  await page.screenshot({ path: `${root}/storage/previews/local-dashboard.png`, fullPage: true });
  await page.getByRole("link", { name: "All invoices", exact: true }).first().click();
  await page.locator("tbody tr").first().waitFor();
  const review = page.locator("tbody tr").first().getByRole("link", { name: /Review|View/ });
  await review.click(); await page.getByRole("heading", { name: "Source document", exact: true }).waitFor();
  await page.screenshot({ path: `${root}/storage/previews/local-detail.png`, fullPage: true });
  await page.getByRole("link", { name: "Overview", exact: true }).click();
  await page.getByRole("region", { name: "Invoice statistics" }).waitFor();
  await page.setViewportSize({ width: 390, height: 844 });
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
  if (overflow) throw new Error("Mobile viewport has horizontal overflow");
  await page.screenshot({ path: `${root}/storage/previews/local-mobile.png`, fullPage: true });
  if (errors.length) throw new Error("Browser JavaScript errors detected");
  console.log("PASS: built local dashboard login, data, invoice navigation and mobile layout; no browser errors or data writes.");
} finally { await browser.close(); }
