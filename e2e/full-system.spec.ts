import { randomUUID } from "node:crypto";
import { test, expect } from "../frontend/node_modules/@playwright/test/index.mjs";
import type { APIRequestContext } from "../frontend/node_modules/@playwright/test/index.mjs";

const adminEmail = process.env.E2E_ADMIN_EMAIL;
const adminPassword = process.env.E2E_ADMIN_PASSWORD;

async function postJson(request: APIRequestContext, url: string, token: string, data: unknown) {
  const response = await request.post(url, {
    headers: { Authorization: "Bearer " + token },
    data,
  });
  expect(response.ok(), `${url} returned ${response.status()}`).toBeTruthy();
  return response.json();
}

async function getAdminAnalytics(request: APIRequestContext, token: string) {
  const response = await request.get("/api/v1/admin/analytics", {
    headers: { Authorization: "Bearer " + token },
  });
  expect(response.ok()).toBeTruthy();
  return response.json();
}

test("admin provisions service, customer joins by QR URL, staff serves, and live updates/notifications arrive", async ({ page, request, browser }) => {
  test.skip(!adminEmail || !adminPassword, "Set E2E_ADMIN_EMAIL and E2E_ADMIN_PASSWORD for the full-system test.");
  const adminLogin = await request.post("/api/v1/auth/login", { data: { email: adminEmail, password: adminPassword } });
  expect(adminLogin.ok()).toBeTruthy();
  const adminToken = (await adminLogin.json()).access_token as string;
  const suffix = randomUUID().slice(0, 8);

  const organization = await postJson(request, "/api/v1/admin/organizations", adminToken, {
    name: `E2E Organization ${suffix}`, slug: `e2e-${suffix}`,
  });
  const branch = await postJson(request, "/api/v1/admin/branches", adminToken, {
    organization_id: organization.id, name: `E2E Branch ${suffix}`,
  });
  const service = await postJson(request, "/api/v1/admin/services", adminToken, {
    branch_id: branch.id, name: `E2E Service ${suffix}`, code: `E${suffix.slice(0, 6)}`,
    average_service_minutes: 5,
  });
  const counter = await postJson(request, "/api/v1/admin/counters", adminToken, {
    branch_id: branch.id, name: "E2E Counter", number: 1, status: "available",
  });
  const queue = await postJson(request, "/api/v1/admin/queues", adminToken, {
    service_id: service.id, name: `E2E Queue ${suffix}`, prefix: "E",
  });
  const completedBefore = (await getAdminAnalytics(request, adminToken)).completed_entries as number;
  const staffPassword = `Staff-${suffix}-Pass`;
  const staff = await postJson(request, "/api/v1/admin/users", adminToken, {
    full_name: `E2E Staff ${suffix}`, email: `staff-${suffix}@example.test`,
    password: staffPassword, role: "staff", organization_id: organization.id, branch_id: branch.id,
  });

  await page.goto("/admin/login");
  await page.getByLabel("Email").fill(adminEmail!);
  await page.getByLabel("Password").fill(adminPassword!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/admin\/dashboard$/);
  await page.goto("/admin/organizations");
  await expect(page.getByRole("heading", { name: "Organizations" })).toBeVisible();
  await expect(page.getByText(organization.name)).toBeVisible();

  const suffixCustomer = `customer-${suffix}@example.test`;
  const customerPassword = `Customer-${suffix}-Pass`;
  await page.goto("/register");
  await page.getByLabel("Full name").fill(`E2E Customer ${suffix}`);
  await page.getByLabel("Email").fill(suffixCustomer);
  await page.getByLabel("Password").fill(customerPassword);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/services$/);
  await page.goto(`/services/${service.id}`);
  await expect(page.getByRole("img", { name: "QueueLess service QR code" })).toBeVisible();
  await page.getByRole("link", { name: "Open join link" }).click();
  await expect(page).toHaveURL(`/join/${branch.id}/${service.id}`);
  await page.getByRole("button", { name: "Confirm and join" }).click();
  await expect(page).toHaveURL(/\/queue\/[^/]+$/);
  const customerQueuePage = page;
  await expect(customerQueuePage.getByText("Status: WAITING")).toBeVisible();
  await expect(customerQueuePage.getByText("Your queue number")).toBeVisible();

  const staffPage = await browser.newPage();
  await staffPage.goto("/staff/login");
  await staffPage.getByLabel("Email").fill(staff.email);
  await staffPage.getByLabel("Password").fill(staffPassword);
  await staffPage.getByRole("button", { name: "Sign in" }).click();
  await expect(staffPage).toHaveURL(/\/staff\/dashboard$/);
  await expect(staffPage.getByRole("heading", { name: "Staff dashboard" })).toBeVisible();
  await staffPage.getByRole("button", { name: "Call", exact: true }).first().click();
  await expect(customerQueuePage.getByText("Status: CALLED")).toBeVisible();
  await expect(staffPage.getByRole("button", { name: "Start", exact: true })).toBeVisible();
  await staffPage.getByRole("button", { name: "Start", exact: true }).click();
  await expect(staffPage.getByRole("button", { name: "Complete", exact: true })).toBeVisible();
  staffPage.on("dialog", (dialog) => dialog.accept());
  await staffPage.getByRole("button", { name: "Complete", exact: true }).click();
  await expect(customerQueuePage.getByText("Status: COMPLETED")).toBeVisible();
  await expect((await getAdminAnalytics(request, adminToken)).completed_entries).toBeGreaterThan(completedBefore);
  await customerQueuePage.goto("/notifications");
  await expect(customerQueuePage.getByText("You joined the queue")).toBeVisible();
  await expect(customerQueuePage.getByText("Your turn is now")).toBeVisible();
  await staffPage.close();
  expect(counter.id).toBeTruthy();
  expect(queue.id).toBeTruthy();
});

test("mobile customer journey renders the service join flow", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/services");
  await expect(page.getByRole("heading").first()).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(375);
});
