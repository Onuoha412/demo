import { defineConfig } from "./frontend/node_modules/@playwright/test/index.mjs";

const baseURL = process.env.E2E_BASE_URL ?? "http://127.0.0.1:5173";
const isExternalTarget = Boolean(process.env.E2E_BASE_URL);

if (isExternalTarget && process.env.E2E_TARGET !== "staging") {
  throw new Error(
    "External E2E targets must be explicitly marked with E2E_TARGET=staging.",
  );
}

if (isExternalTarget && !process.env.E2E_API_URL) {
  throw new Error("Set E2E_API_URL to the staging API origin for external E2E runs.");
}

export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  reporter: "list",
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "chromium", use: { browserName: "chromium" } },
    { name: "firefox", use: { browserName: "firefox" } },
    { name: "webkit", use: { browserName: "webkit" } },
  ],
  ...(isExternalTarget
    ? {}
    : {
        webServer: {
          command: "npm run dev --prefix frontend -- --host 127.0.0.1",
          url: baseURL,
          reuseExistingServer: !process.env.CI,
          timeout: 30_000,
        },
      }),
});
