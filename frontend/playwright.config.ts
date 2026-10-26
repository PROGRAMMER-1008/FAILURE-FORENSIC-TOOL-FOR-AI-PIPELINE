import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "e2e",
  use: {
    baseURL: process.env.FF_BROWSER_URL || "http://127.0.0.1:8000",
    headless: true,
  },
  reporter: "list",
  timeout: 30000,
});
