import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

import { StaffDashboardPage } from "../pages/staff/StaffDashboardPage";
import { useAuthStore } from "../store/authStore";

vi.mock("../hooks/useQueueWebSocket", () => ({
  useQueueWebSocket: () => ({ status: "connected", lastEventAt: null, event: undefined }),
}));

const queueEntry = {
  id: "entry-2",
  queue_id: "queue-2",
  queue_prefix: "B",
  queue_number: 7,
  status: "waiting",
  people_ahead: 0,
  estimated_wait_minutes: 0,
  counter_id: null,
  counter: null,
  joined_at: new Date().toISOString(),
  called_at: null,
  service_started_at: null,
  completed_at: null,
};

beforeEach(() => {
  useAuthStore.setState({
    token: "staff-token",
    user: {
      id: "staff-1",
      full_name: "Branch Staff",
      email: "staff@example.test",
      role: "staff",
      organization_id: null,
      branch_id: "branch-1",
      created_at: new Date().toISOString(),
    },
    ready: true,
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

it("lets staff switch queues and calls the next customer at the selected counter", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = new URL(String(input), window.location.origin);
    if (url.pathname.endsWith("/api/v1/staff/dashboard")) {
      return Response.json({
        branch: { id: "branch-1", name: "Main branch" },
        counters: [{ id: "counter-1", name: "Counter 1", number: 1, status: "available" }],
        queues: [
          { id: "queue-1", name: "Admissions", prefix: "A", status: "open", waiting_count: 0, serving_count: 0, completed_count: 0, skipped_count: 0 },
          { id: "queue-2", name: "Payments", prefix: "B", status: "open", waiting_count: 1, serving_count: 0, completed_count: 0, skipped_count: 0 },
        ],
      });
    }
    if (url.pathname.endsWith("/api/v1/staff/queues/queue-1")) {
      return Response.json({ id: "queue-1", name: "Admissions", status: "open", entries: [] });
    }
    if (url.pathname.endsWith("/api/v1/staff/queues/queue-2")) {
      return Response.json({ id: "queue-2", name: "Payments", status: "open", entries: [queueEntry] });
    }
    if (url.pathname.endsWith("/api/v1/queue-requests/review")) {
      return Response.json({ items: [], total: 0, pending_total: 0, page: 1, page_size: 50 });
    }
    if (url.pathname.endsWith("/api/v1/queues/queue-2/next") && init?.method === "POST") {
      return Response.json({ ...queueEntry, status: "called", counter_id: "counter-1" });
    }
    throw new Error(`Unexpected request: ${url.pathname}`);
  });
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <StaffDashboardPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );

  const queueSelector = await screen.findByRole("combobox", { name: "Queue" });
  fireEvent.change(queueSelector, { target: { value: "queue-2" } });
  expect(await screen.findAllByText("B007")).toHaveLength(2);
  fireEvent.click(screen.getByRole("button", { name: "Next" }));

  await waitFor(() => {
    const nextCall = fetchMock.mock.calls.find(([input, init]) => {
      const url = new URL(String(input), window.location.origin);
      return url.pathname.endsWith("/api/v1/queues/queue-2/next") && init?.method === "POST";
    });
    expect(nextCall).toBeDefined();
    expect(JSON.parse(String(nextCall?.[1]?.body))).toEqual({ counter_id: "counter-1" });
  });
});

it("loads the dedicated branch customer screen", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = new URL(String(input), window.location.origin);
    if (url.pathname.endsWith("/api/v1/staff/customers")) {
      return Response.json([
        {
          entry_id: "entry-1",
          queue_id: "queue-1",
          queue_name: "Admissions",
          queue_prefix: "A",
          queue_number: 12,
          status: "serving",
          joined_at: new Date().toISOString(),
          customer: {
            id: "customer-1",
            full_name: "Sam Customer",
            email: "sam@example.test",
          },
        },
      ]);
    }
    if (url.pathname.endsWith("/api/v1/queue-requests/review")) {
      return Response.json({ items: [], total: 0, pending_total: 0, page: 1, page_size: 50 });
    }
    throw new Error(`Unexpected request: ${url.pathname}`);
  });
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/staff/customers"]}>
        <StaffDashboardPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );

  expect(await screen.findByRole("heading", { name: "Customers" })).toBeInTheDocument();
  expect(await screen.findByText("Sam Customer")).toBeInTheDocument();
  expect(screen.getByText("A012")).toBeInTheDocument();
  expect(screen.getByText("sam@example.test")).toBeInTheDocument();
});

it("loads the dedicated queue history screen", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = new URL(String(input), window.location.origin);
    if (url.pathname.endsWith("/api/v1/staff/history")) {
      return Response.json([
        {
          entry_id: "entry-1",
          queue_id: "queue-1",
          queue_name: "Admissions",
          queue_prefix: "A",
          queue_number: 12,
          status: "completed",
          joined_at: new Date().toISOString(),
          completed_at: new Date().toISOString(),
          customer: {
            id: "customer-1",
            full_name: "Sam Customer",
            email: "sam@example.test",
          },
        },
      ]);
    }
    if (url.pathname.endsWith("/api/v1/queue-requests/review")) {
      return Response.json({ items: [], total: 0, pending_total: 0, page: 1, page_size: 50 });
    }
    throw new Error(`Unexpected request: ${url.pathname}`);
  });
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/staff/history"]}>
        <StaffDashboardPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );

  expect(await screen.findByRole("heading", { name: "Queue history" })).toBeInTheDocument();
  expect(await screen.findByText("Admissions")).toBeInTheDocument();
  expect(screen.getByText("Sam Customer")).toBeInTheDocument();
  expect(screen.getByText("A012")).toBeInTheDocument();
});
