import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./public-tests", outputDir: "./test-results/public", workers: 1, timeout: 90000, expect: { timeout: 15000 },
  use: { baseURL: "http://localhost:3002", viewport: { width: 1440, height: 1000 }, screenshot: "only-on-failure", video: "on" },
  webServer: process.env.PUBLIC_PREVIEW === "true" ? undefined : [
    { command: process.platform === "win32" ? "..\\.venv\\Scripts\\python.exe ..\\scripts\\public_api.py" : "../.venv/bin/python ../scripts/public_api.py", url: "http://127.0.0.1:8002/health", reuseExistingServer: false, timeout: 60000 },
    { command: "npm run dev -- --port 3002", env: { NEXT_PUBLIC_API_BASE_URL: "http://127.0.0.1:8002" }, url: "http://localhost:3002", reuseExistingServer: false, timeout: 120000 },
  ],
});
