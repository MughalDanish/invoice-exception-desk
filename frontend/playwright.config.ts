import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests", workers: 1, timeout: 120000, retries: 0, expect: { timeout: 15000 },
  globalTeardown: "./tests/teardown.ts",
  use: { baseURL: "http://localhost:3001", viewport: { width: 1440, height: 1000 }, trace: "retain-on-failure", screenshot: "only-on-failure" },
  webServer: [
    { command: process.platform === "win32" ? "..\\.venv\\Scripts\\python.exe ..\\scripts\\browser_api.py" : "../.venv/bin/python ../scripts/browser_api.py", url: "http://127.0.0.1:8001/health", reuseExistingServer: false, timeout: 120000 },
    { command: "npm run dev -- --port 3001", env: { NEXT_PUBLIC_API_BASE_URL: "http://127.0.0.1:8001" }, url: "http://localhost:3001", reuseExistingServer: false, timeout: 120000 },
  ],
});
