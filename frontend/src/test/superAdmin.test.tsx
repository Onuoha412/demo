import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import App from "../App";
import { AdminQueuePage } from "../pages/admin/AdminQueuePage";
import { AdminResourcePage } from "../pages/admin/AdminResourcePage";
import { useAuthStore } from "../store/authStore";

class TestWebSocket {
  static instances: TestWebSocket[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;

  constructor(readonly url: string) {
    TestWebSocket.instances.push(this);
  }

  close() {
    this.onclose?.({ code: 1000 } as CloseEvent);
  }
}

vi.mock("../hooks/useQueueWebSocket", () => ({
  useQueueWebSocket: () => ({ status: "connected", lastEventAt: null, event: undefined }),
}));

let setupOrganizationCount = 1;
let announcementPublished = false;

function renderApp(path: string) {
  window.history.pushState({}, "", path);
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  TestWebSocket.instances = [];
  setupOrganizationCount = 1;
  announcementPublished = false;
  sessionStorage.clear();
  const backupInventory = Array.from({ length: 7 }, (_, index) => ({
    filename: `queueless-20261015T12000${index}Z-12345678.sqlite3`,
    size_bytes: 1024 * (index + 1),
    created_at: new Date(Date.now() - index * 60_000).toISOString(),
  }));
  useAuthStore.setState({
    token: "super-admin-session",
    user: {
      id: "super-admin-1",
      full_name: "Platform Owner",
      email: "owner@example.test",
      role: "super_admin",
      organization_id: null,
      created_at: new Date().toISOString(),
    },
    ready: true,
  });
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    if (url.endsWith("/api/v1/admin/announcements")) {
      if (init?.method === "POST") {
        return Response.json(
          {
            id: "org-announcement-1",
            organization_id: "organization-1",
            title: "Team briefing",
            body: "Meet at 09:00.",
            audience: "staff",
            published_at: null,
            expires_at: null,
            created_at: new Date().toISOString(),
          },
          { status: 201 },
        );
      }
      return Response.json([]);
    }
    if (url.endsWith("/api/v1/super-admin/dashboard")) {
      return Response.json({
        users: { customer: 2, staff: 1, admin: 1, super_admin: 1 },
        organizations: setupOrganizationCount,
        branches: 2,
        services: 3,
        counters: 2,
        queues: { waiting: 3, serving: 1, completed: 4, skipped: 0, cancelled: 0 },
        recent_events: [],
      });
    }
    if (url.endsWith("/api/v1/super-admin/system-health")) {
      return Response.json({
        api: "ok",
        database: "connected",
        backup_monitoring: "not_configured",
      });
    }
    if (url.endsWith("/api/v1/super-admin/backups")) {
      return init?.method === "POST"
        ? Response.json({
            filename: "queueless-20261015T120000Z-12345678.sqlite3",
            size_bytes: 1024,
            created_at: new Date().toISOString(),
          })
        : Response.json(backupInventory);
    }
    if (url.endsWith("/api/v1/super-admin/initial-setup")) {
      setupOrganizationCount = 1;
      return Response.json(
        {
          organization_id: "organization-1",
          branch_id: "branch-1",
          service_id: "service-1",
          queue_id: "queue-1",
        },
        { status: 201 },
      );
    }
    if (url.endsWith("/api/v1/super-admin/ws-ticket")) {
      return Response.json({ ticket: "one-time-super-admin-ticket" });
    }
    if (url.endsWith("/api/v1/super-admin/announcements")) {
      if (init?.method === "POST") {
        return Response.json(
          {
            id: "announcement-new",
            title: "Service update",
            body: "New hours today.",
            audience: "all",
            published_at: null,
            expires_at: null,
            created_at: new Date().toISOString(),
          },
          { status: 201 },
        );
      }
      return Response.json([
        {
          id: "announcement-1",
          title: "Service update",
          body: "New hours today.",
          audience: "all",
          published_at: announcementPublished ? new Date().toISOString() : null,
          expires_at: null,
          created_at: new Date().toISOString(),
        },
      ]);
    }
    if (url.includes("/api/v1/super-admin/announcements/announcement-1/")) {
      announcementPublished = url.endsWith("/publish");
      return Response.json({
        id: "announcement-1",
        title: "Service update",
        body: "New hours today.",
        audience: "all",
        published_at: announcementPublished ? new Date().toISOString() : null,
        expires_at: null,
        created_at: new Date().toISOString(),
      });
    }
    if (url.endsWith("/api/v1/super-admin/platform-settings")) {
      return Response.json({
        maintenance_mode:
          init?.method === "PUT"
            ? JSON.parse(String(init.body)).maintenance_mode
            : false,
        maintenance_message:
          init?.method === "PUT"
            ? JSON.parse(String(init.body)).maintenance_message
            : "Scheduled maintenance.",
        updated_at: new Date().toISOString(),
      });
    }
    if (url.includes("/api/v1/admin/queues?")) {
      return Response.json({
        items: [{ id: "queue-1", name: "Admissions", status: "open" }],
        total: 1,
        page: 1,
        page_size: 20,
      });
    }
    if (url.includes("/api/v1/admin/queues/queue-1/entries?")) {
      return Response.json({
        id: "queue-1",
        name: "Admissions",
        prefix: "A",
        status: "open",
        service_id: "service-1",
        service_name: "Admissions service",
        branch_id: "branch-1",
        total_entries: 0,
        page: 1,
        page_size: 50,
        entries: [],
      });
    }
    throw new Error(`Unexpected request: ${url}`);
  });
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

it("loads the protected Super Admin overview at the documented route", async () => {
  renderApp("/super-admin/dashboard");

  expect(
    await screen.findByRole("heading", { name: "Super Admin" }),
  ).toBeInTheDocument();
  expect(screen.getByText("Global control center")).toBeInTheDocument();
  expect(screen.getByText("Super Admins")).toBeInTheDocument();
  expect(screen.getByText("Services")).toBeInTheDocument();
  expect(screen.getByText("Cancelled")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Backup inventory" })).toBeInTheDocument();
  expect(
    await screen.findByText("7 recent verified snapshots"),
  ).toBeInTheDocument();
  expect(
    screen.getByText("queueless-20261015T120006Z-12345678.sqlite3"),
  ).toBeInTheDocument();
  expect(await screen.findByText("connected")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Manage users" })).toHaveAttribute(
    "href",
    "/super-admin/users",
  );
});

it("manages published announcements and maintenance settings", async () => {
  renderApp("/super-admin/operations");

  expect(
    await screen.findByRole("heading", { name: "Announcements & operations" }),
  ).toBeInTheDocument();
  expect(await screen.findByText("Service update")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Publish" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Announcement published.");

  fireEvent.click(screen.getByRole("checkbox", { name: /enable maintenance mode/i }));
  fireEvent.click(screen.getByRole("button", { name: "Save system settings" }));
  await waitFor(() => {
    const settingsRequest = vi.mocked(globalThis.fetch).mock.calls.find(
      ([input, init]) =>
        String(input).endsWith("/api/v1/super-admin/platform-settings") &&
        init?.method === "PUT",
    );
    expect(settingsRequest).toBeDefined();
    expect(JSON.parse(String(settingsRequest?.[1]?.body))).toMatchObject({
      maintenance_mode: true,
      maintenance_message: "Scheduled maintenance.",
    });
  });
});

it("lets organization admins create scoped staff announcements", async () => {
  useAuthStore.setState({
    token: "organization-admin-session",
    user: {
      id: "admin-1",
      full_name: "Organization Admin",
      email: "admin@example.test",
      role: "admin",
      organization_id: "organization-1",
      created_at: new Date().toISOString(),
    },
    ready: true,
  });
  renderApp("/admin/announcements");

  expect(
    await screen.findByRole("heading", { name: "Staff announcements" }),
  ).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Title"), {
    target: { value: "Team briefing" },
  });
  fireEvent.change(screen.getByLabelText("Message"), {
    target: { value: "Meet at 09:00." },
  });
  fireEvent.click(screen.getByRole("button", { name: "Save draft" }));

  expect(await screen.findByRole("status")).toHaveTextContent(
    "Announcement saved as a draft.",
  );
  const request = vi.mocked(globalThis.fetch).mock.calls.find(
    ([input, init]) =>
      String(input).endsWith("/api/v1/admin/announcements") &&
      init?.method === "POST",
  );
  expect(JSON.parse(String(request?.[1]?.body))).toMatchObject({
    title: "Team briefing",
    body: "Meet at 09:00.",
    audience: "staff",
  });
});

it("guides the first Super Admin login through real workspace setup", async () => {
  setupOrganizationCount = 0;
  renderApp("/super-admin/dashboard");

  expect(
    await screen.findByRole("heading", { name: "Set up your organization" }),
  ).toBeInTheDocument();
  expect(
    screen.getByText(/No sample records are added/),
  ).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("Organization name"), {
    target: { value: "Example Health" },
  });
  expect(screen.getByLabelText("Organization URL slug")).toHaveValue(
    "example-health",
  );
  fireEvent.change(screen.getByLabelText("Branch name"), {
    target: { value: "Central" },
  });
  fireEvent.change(screen.getByLabelText("Time zone"), {
    target: { value: "Europe/London" },
  });
  fireEvent.change(screen.getByLabelText("Service name"), {
    target: { value: "Appointments" },
  });
  fireEvent.change(screen.getByLabelText("Service code"), {
    target: { value: "APT" },
  });
  fireEvent.change(screen.getByLabelText("Queue name"), {
    target: { value: "Appointments queue" },
  });
  fireEvent.change(screen.getByLabelText("Queue ticket prefix"), {
    target: { value: "A" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Create my workspace" }));

  expect(
    await screen.findByText(
      "The organization, branch, service, and open queue were created.",
    ),
  ).toBeInTheDocument();
  const setupRequest = vi
    .mocked(globalThis.fetch)
    .mock.calls.find(([input]) =>
      String(input).endsWith("/api/v1/super-admin/initial-setup"),
    );
  expect(setupRequest?.[1]?.method).toBe("POST");
  expect(JSON.parse(String(setupRequest?.[1]?.body))).toMatchObject({
    organization_name: "Example Health",
    organization_slug: "example-health",
    branch_name: "Central",
    timezone: "Europe/London",
    service_name: "Appointments",
    service_code: "APT",
    queue_name: "Appointments queue",
    queue_prefix: "A",
  });
});

it("uses an authenticated live socket to refresh platform queue metrics", async () => {
  vi.stubGlobal("WebSocket", TestWebSocket);
  renderApp("/super-admin/dashboard");

  expect(
    await screen.findByRole("heading", { name: "Super Admin" }),
  ).toBeInTheDocument();
  await waitFor(() => expect(TestWebSocket.instances).toHaveLength(1));
  expect(TestWebSocket.instances[0].url).toContain(
    "/ws/super-admin?ticket=one-time-super-admin-ticket",
  );
  const dashboardRequests = () =>
    vi
      .mocked(globalThis.fetch)
      .mock.calls.filter(([input]) =>
        String(input).endsWith("/api/v1/super-admin/dashboard"),
      ).length;
  const before = dashboardRequests();
  await act(async () => {
    TestWebSocket.instances[0].onopen?.();
  });
  expect(await screen.findByText("Platform events: connected")).toBeInTheDocument();
  await waitFor(() => expect(dashboardRequests()).toBeGreaterThan(before));

  const beforeEvent = dashboardRequests();
  await act(async () => {
    TestWebSocket.instances[0].onmessage?.({
      data: JSON.stringify({ event: "CUSTOMER_JOINED" }),
    } as MessageEvent);
  });
  await waitFor(() => expect(dashboardRequests()).toBeGreaterThan(beforeEvent));
});

it("does not render the Super Admin dashboard without a Super Admin session", async () => {
  useAuthStore.setState((state) => ({
    ...state,
    user: { ...state.user!, role: "admin" },
  }));
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify({
        customers_served_today: 0,
        customers_waiting: 0,
        average_waiting_time: 0,
        average_service_time: 0,
        completion_rate: 0,
        skip_rate: 0,
        cancellation_rate: 0,
        busiest_service: null,
        busiest_hour: null,
      }),
      { headers: { "Content-Type": "application/json" } },
    ),
  );
  renderApp("/super-admin/dashboard");

  await waitFor(() =>
    expect(window.location.pathname).toBe("/admin/dashboard"),
  );
  expect(
    screen.queryByRole("heading", { name: "Global control center" }),
  ).not.toBeInTheDocument();
});

it("keeps the queue audit link inside the Super Admin area", async () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/super-admin/queues"]}>
        <Routes>
          <Route path="/super-admin/:resource" element={<AdminResourcePage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );

  expect(await screen.findByRole("link", { name: "View requests" })).toHaveAttribute(
    "href",
    "/super-admin/queues/queue-1/entries",
  );
});

it("opens queue audit details and returns to Super Admin queue management", async () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/super-admin/queues/queue-1/entries"]}>
        <Routes>
          <Route
            path="/super-admin/queues/:queueId/entries"
            element={<AdminQueuePage />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );

  expect(await screen.findByRole("heading", { name: "Admissions" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Back to queues" })).toHaveAttribute(
    "href",
    "/super-admin/queues",
  );
});
