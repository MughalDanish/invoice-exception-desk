import { defineConfig } from "@playwright/test";
// Uses the installed TS transformer/assertions only; no browser, API or database.
export default defineConfig({
  testDir: "./unit-tests",
  outputDir: "./test-results/unit",
  workers: 1,
});
