import { randomUUID } from "node:crypto";
import { test, expect } from "../frontend/node_modules/@playwright/test/index.mjs";
import type { APIRequestContext } from "../frontend/node_modules/@playwright/test/index.mjs";

const adminEmail = process.env.E2E_ADMIN_EMAIL;
const adminPassword = process.env.E2E_ADMIN_PASSWORD;
const apiBaseUrl =
  process.env.E2E_API_URL ?? process.env.E2E_BASE_URL ?? "http://127.0.0.1:5173";

function apiUrl(path: string): string {
  return new URL(path, apiBaseUrl).toString();
}

async function postJson(request: APIRequestContext, url: string, token: string, data: unknown) {
  const response = await request.post(apiUrl(url), {
    headers: { Authorization: "Bearer " + token },
    data,
  });
  expect(response.ok(), `${url} returned ${response.status()}`).toBeTruthy();
  return response.json();
}

async function getAdminAnalytics(request: APIRequestContext, token: string) {
  const response = await request.get(apiUrl("/api/v1/admin/analytics"), {
    headers: { Authorization: "Bearer " + token },
  });
  expect(response.ok()).toBeTruthy();
  return response.json();
}

test("customer, staff, public display, and admin stay in sync through service", async ({ page, request, browser, browserName }) => {
  test.skip(
    !adminEmail || !adminPassword || process.env.E2E_DATA_DISPOSABLE !== "1",
    "Set staging admin credentials and E2E_DATA_DISPOSABLE=1 for the mutating full-system test.",
  );
  test.skip(
    browserName !== "chromium",
    "The mutating full-system journey runs once in Chromium; mobile smoke coverage runs in every browser.",
  );
  const adminLogin = await request.post(apiUrl("/api/v1/auth/login"), {
    data: { email: adminEmail, password: adminPassword },
  });
  expect(adminLogin.ok()).toBeTruthy();
  const adminToken = (await adminLogin.json()).session_token as string;
  const suffix = randomUUID().slice(0, 8);

  const organization = await postJson(request, "/api/v1/admin/organizations", adminToken, {
    name: `E2E Organization ${suffix}`, slug: `e2e-${suffix}`,
  });
  const branch = await postJson(request, "/api/v1/admin/branches", adminToken, {
    organization_id: organization.id, name: `E2E Branch ${suffix}`,
  });
  const reassignmentBranch = await postJson(
    request,
    "/api/v1/admin/branches",
    adminToken,
    { organization_id: organization.id, name: `E2E Reassignment ${suffix}` },
  );
  const service = await postJson(request, "/api/v1/admin/services", adminToken, {
    branch_id: branch.id, name: `E2E Service ${suffix}`, code: `E${suffix.slice(0, 6)}`,
    average_service_minutes: 5,
  });
  const appointmentStart = new Date(Date.now() + 10 * 60_000);
  await postJson(request, "/api/v1/admin/appointment-slots", adminToken, {
    service_id: service.id,
    starts_at: appointmentStart.toISOString(),
    ends_at: new Date(appointmentStart.getTime() + 30 * 60_000).toISOString(),
    capacity: 1,
  });
  const counter = await postJson(request, "/api/v1/admin/counters", adminToken, {
    branch_id: branch.id, name: "Counter 2", number: 2, status: "available",
  });
  const queue = await postJson(request, "/api/v1/admin/queues", adminToken, {
    service_id: service.id, name: `E2E Queue ${suffix}`, prefix: "A",
  });
  const servedBefore = (await getAdminAnalytics(request, adminToken)).customers_served_today as number;
  const staffPassword = `Staff-${suffix}-Pass`;
  const staff = await postJson(request, "/api/v1/admin/users", adminToken, {
    full_name: `E2E Staff ${suffix}`, email: `staff-${suffix}@example.test`,
    password: staffPassword, role: "staff", organization_id: organization.id, branch_id: branch.id,
  });

  const customerPage = await browser.newPage();
  const staffPage = await browser.newPage();
  const displayPage = await browser.newPage();

  await page.goto("/admin/login");
  await page.getByLabel("Email").fill(adminEmail!);
  await page.getByLabel("Password").fill(adminPassword!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/admin\/dashboard$/);
  await expect(page.getByText("Average wait (min)")).toBeVisible();
  const organizations = await request.get(apiUrl("/api/v1/admin/organizations"), {
    headers: { Authorization: `Bearer ${adminToken}` },
  });
  expect(organizations.ok()).toBeTruthy();
  expect((await organizations.json()).items.some((item: { name: string }) => item.name === organization.name)).toBe(true);

  const suffixCustomer = `customer-${suffix}@example.test`;
  const customerPassword = `Customer-${suffix}-Pass`;
  await customerPage.goto("/register");
  await customerPage.getByLabel("Full name").fill(`E2E Customer ${suffix}`);
  await customerPage.getByLabel("Email").fill(suffixCustomer);
  await customerPage.locator("#register-password").fill(customerPassword);
  await customerPage.locator("#register-confirm-password").fill(customerPassword);
  await customerPage.getByRole("button", { name: "Create account" }).click();
  await expect(customerPage).toHaveURL(/\/services$/);
  await expect(
    customerPage.getByRole("heading", { name: "Available services" }),
  ).toBeVisible();
  await customerPage.goto(`/services/${service.id}/appointments`);
  await expect(
    customerPage.getByRole("heading", { name: "Book an appointment" }),
  ).toBeVisible();
  await customerPage.getByRole("button", { name: "Book this time" }).click();
  await expect(customerPage.getByText(/booked/)).toBeVisible();
  await customerPage.goto("/appointments");
  await customerPage.getByRole("button", { name: "Check in" }).click();
  await expect(customerPage.getByText(/checked in/)).toBeVisible();

  await customerPage.goto(`/services/${service.id}`);
  await expect(customerPage.getByRole("img", { name: "QueueLess service QR code" })).toBeVisible();
  await customerPage.getByRole("link", { name: "Open join link" }).click();
  await expect(customerPage).toHaveURL(`/join/${branch.id}/${service.id}`);
  await customerPage.getByRole("button", { name: "Confirm and join" }).click();
  await expect(customerPage).toHaveURL(/\/queue\/[^/]+$/);
  const customerQueuePage = customerPage;
  await expect(customerQueuePage.getByText("Status: WAITING")).toBeVisible();
  await expect(customerQueuePage.getByText("A001")).toBeVisible();
  await expect(customerQueuePage.getByText("Predictive/statistical estimation")).toBeVisible();

  for (let index = 0; index < 3; index += 1) {
    const registration = await request.post(apiUrl("/api/v1/auth/register"), {
      data: {
        full_name: `E2E Waiting Customer ${index + 1} ${suffix}`,
        email: `waiting-${index + 1}-${suffix}@example.test`,
        password: `Waiting-${index + 1}-${suffix}-Pass`,
      },
    });
    expect(registration.status()).toBe(201);
    const sessionToken = (await registration.json()).session_token as string;
    await postJson(
      request,
      `/api/v1/customers/services/${service.id}/join?branch_id=${branch.id}`,
      sessionToken,
      {},
    );
  }

  await staffPage.goto("/staff/login");
  await staffPage.getByLabel("Email").fill(staff.email);
  await staffPage.getByLabel("Password").fill(staffPassword);
  await staffPage.getByRole("button", { name: "Sign in" }).click();
  await expect(staffPage).toHaveURL(/\/staff\/dashboard$/);
  await expect(staffPage.getByRole("heading", { name: "Staff dashboard" })).toBeVisible();
  await staffPage.getByLabel("Counter").selectOption({ label: "Counter 2" });
  await expect(staffPage.getByText("Waiting", { exact: true }).first()).toBeVisible();
  await expect(
    staffPage.getByText("Waiting", { exact: true }).first().locator("..").locator("p").nth(1),
  ).toHaveText("4");

  await displayPage.goto(`/display/${queue.id}`);
  await expect(displayPage.getByText("A002")).toBeVisible();
  await expect(displayPage.getByText("A003")).toBeVisible();
  await expect(displayPage.getByText("A004")).toBeVisible();
  const nowServing = displayPage.getByText("Now serving").locator("..");
  await expect(nowServing).toContainText("—");

  await staffPage.getByRole("button", { name: "CALL", exact: true }).click();
  await expect(customerQueuePage.getByText("You have been called.")).toBeVisible();
  await expect(customerQueuePage.getByText("Proceed to Counter 2.")).toBeVisible();
  await expect(customerQueuePage.getByText("Status: CALLED")).toBeVisible();
  await expect(
    customerQueuePage.getByText("A001").locator(".."),
  ).toContainText("CALLED");
  await expect(nowServing).toContainText("A001");
  await expect(nowServing).toContainText("Counter 2");

  await expect(staffPage.getByRole("button", { name: "Start", exact: true })).toBeVisible();
  await expect(staffPage.getByRole("button", { name: "Complete", exact: true })).toBeVisible();
  staffPage.on("dialog", (dialog) => dialog.accept());
  await staffPage.getByRole("button", { name: "Complete", exact: true }).click();
  await expect(customerQueuePage.getByText("Status: COMPLETED")).toBeVisible();
  await expect(customerQueuePage.getByText("Service completed ✓")).toBeVisible();
  await expect(nowServing).toContainText("A002");
  await expect(nowServing).toContainText("Counter 2");

  const analytics = await getAdminAnalytics(request, adminToken);
  await page.reload();
  await expect(page.getByText("Completed today", { exact: true }).locator("..").locator("p").nth(1))
    .toHaveText(String(servedBefore + 1));
  expect(analytics.customers_served_today).toBe(servedBefore + 1);
  const reassigned = await request.patch(
    apiUrl(`/api/v1/admin/users/${staff.id}`),
    {
      headers: { Authorization: `Bearer ${adminToken}` },
      data: { branch_id: reassignmentBranch.id },
    },
  );
  expect(reassigned.ok()).toBeTruthy();
  expect((await reassigned.json()).branch_id).toBe(reassignmentBranch.id);
  const restored = await request.patch(
    apiUrl(`/api/v1/admin/users/${staff.id}`),
    {
      headers: { Authorization: `Bearer ${adminToken}` },
      data: { branch_id: branch.id },
    },
  );
  expect(restored.ok()).toBeTruthy();
  expect((await restored.json()).branch_id).toBe(branch.id);
  await customerQueuePage.goto("/notifications");
  await expect(customerQueuePage.getByText("You joined the queue")).toBeVisible();
  await expect(customerQueuePage.getByText("Your turn is now")).toBeVisible();
  await expect(customerQueuePage.getByText(/Proceed to Counter 2/)).toBeVisible();
  expect(counter.id).toBeTruthy();
  expect(queue.id).toBeTruthy();
});

test("mobile customer journey renders the service join flow", async ({ page }) => {
  await page.route("**/api/v1/catalog/**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
  );
  await page.setViewportSize({ width: 320, height: 812 });
  await page.goto("/services", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading").first()).toBeVisible();
  for (const width of [320, 375, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await expect
      .poll(() => page.evaluate(() => document.documentElement.scrollWidth))
      .toBeLessThanOrEqual(width);
  }
});
