import { defineConfig } from "@playwright/test";
// Presentation-only fixture checks. No API process, database or model calls.
export default defineConfig({
  testDir: "./visual-tests", outputDir: "./test-results/visual", workers: 1,
  timeout: 120000, retries: 0, expect: { timeout: 15000 },
  use: { baseURL: "http://localhost:3003", viewport: { width: 1440, height: 1000 }, screenshot: "only-on-failure" },
  webServer: { command: "npm run dev -- --port 3003", env: { NEXT_PUBLIC_API_BASE_URL: "http://localhost:8999" }, url: "http://localhost:3003", reuseExistingServer: false, timeout: 120000 },
});
