import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { AdminDashboardPage } from "../pages/admin/AdminDashboardPage";
import { useAuthStore } from "../store/authStore";

beforeEach(() => {
  useAuthStore.setState({
    token: "admin-session",
    user: {
      id: "admin-1",
      full_name: "Branch Administrator",
      email: "admin@example.test",
      role: "admin",
      organization_id: null,
      created_at: new Date().toISOString(),
    },
    ready: true,
  });

  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = new URL(String(input), window.location.origin);
    if (url.pathname.endsWith("/api/v1/admin/analytics")) {
      return Response.json({
        customers_served_today: 12,
        customers_waiting: 4,
        completed_entries: 18,
        waiting_entries: 4,
        average_waiting_time: 8,
        average_service_time: 6,
        completion_rate: 75,
        skip_rate: 10,
        cancellation_rate: 5,
        busiest_service: { name: "Admissions", count: 8 },
        busiest_hour: { hour: 10, count: 5 },
      });
    }
    if (url.pathname.endsWith("/api/v1/admin/reports/queue-entries.csv")) {
      return new Response("entry_id,ticket\n", {
        headers: { "Content-Type": "text/csv" },
      });
    }
    if (url.pathname.endsWith("/api/v1/admin/queues")) {
      return Response.json({ items: [], total: 0, page: 1, page_size: 100 });
    }
    if (url.pathname.endsWith("/api/v1/queue-requests/review")) {
      return Response.json({
        items: [],
        total: 0,
        pending_total: 0,
        page: 1,
        page_size: 50,
      });
    }
    throw new Error(`Unexpected request: ${url.pathname}`);
  });
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

it("loads admin analytics and queue-request review on the dashboard route", async () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  const fetchMock = vi.mocked(globalThis.fetch);
  render(
    <QueryClientProvider client={queryClient}>
      <AdminDashboardPage />
    </QueryClientProvider>,
  );

  expect(
    await screen.findByRole("heading", { name: "Admin dashboard" }),
  ).toBeInTheDocument();
  expect(screen.getByText("Completed today")).toBeInTheDocument();
  expect(screen.getByText("Queue volume")).toBeInTheDocument();
  expect(await screen.findByText("Customer requests")).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("Analytics start date"), {
    target: { value: "2026-10-01" },
  });
  fireEvent.change(screen.getByLabelText("Analytics end date"), {
    target: { value: "2026-10-07" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Apply dates" }));
  await waitFor(() => {
    const analyticsRequest = fetchMock.mock.calls
      .map(([input]) => new URL(String(input), window.location.origin))
      .find((url) => url.pathname.endsWith("/api/v1/admin/analytics") && url.searchParams.has("start"));
    expect(analyticsRequest?.searchParams.get("start")).toBe("2026-10-01T00:00:00Z");
    expect(analyticsRequest?.searchParams.get("end")).toBe("2026-10-07T23:59:59.999Z");
  });

  const createObjectUrl = vi.fn(() => "blob:queue-report");
  const revokeObjectUrl = vi.fn();
  vi.stubGlobal(
    "URL",
    Object.assign(URL, {
      createObjectURL: createObjectUrl,
      revokeObjectURL: revokeObjectUrl,
    }),
  );
  const anchorClick = vi
    .spyOn(HTMLAnchorElement.prototype, "click")
    .mockImplementation(() => {});
  fireEvent.click(
    await screen.findByRole("button", { name: "Download queue report (CSV)" }),
  );
  await waitFor(() => {
    const reportRequest = fetchMock.mock.calls
      .map(([input]) => new URL(String(input), window.location.origin))
      .find((url) => url.pathname.endsWith("/api/v1/admin/reports/queue-entries.csv"));
    expect(reportRequest?.searchParams.get("start")).toBe("2026-10-01T00:00:00Z");
    expect(reportRequest?.searchParams.get("end")).toBe("2026-10-07T23:59:59.999Z");
    expect(anchorClick).toHaveBeenCalledOnce();
    expect(createObjectUrl).toHaveBeenCalledOnce();
  });
});
