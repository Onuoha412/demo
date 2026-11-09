import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

import { MyQueueRequestsPanel } from "../components/queue/MyQueueRequestsPanel";
import { QueueRequestReviewPanel } from "../components/queue/QueueRequestReviewPanel";
import type { QueueRequest } from "../services/queueRequests";
import { useAuthStore } from "../store/authStore";

const branch = {
  id: "branch-1",
  organization_id: "org-1",
  name: "Main branch",
  address: null,
  timezone: "UTC",
};

const customerRequest = {
  id: "request-1",
  customer: {
    id: "customer-1",
    full_name: "Queue Customer",
    email: "customer@example.test",
  },
  branch_id: "branch-1",
  branch_name: "Main branch",
  request_text: "I need help with a general account issue.",
  status: "pending" as const,
  assigned_queue_id: null,
  assigned_queue_name: null,
  queue_entry_id: null,
  queue_number: null,
  queue_prefix: null,
  review_note: null,
  reviewed_at: null,
  created_at: new Date().toISOString(),
};

function renderWithProviders(component: React.ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{component}</MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.restoreAllMocks();
  useAuthStore.setState({
    token: "customer-token",
    user: {
      id: "customer-1",
      full_name: "Queue Customer",
      email: "customer@example.test",
      role: "customer",
      organization_id: null,
      created_at: new Date().toISOString(),
    },
    ready: true,
  });
});

it("lets a customer submit a free-form branch request and see its pending card", async () => {
  let requests: typeof customerRequest[] = [];
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(
    async (input, init) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.includes("/api/v1/catalog/branches")) {
        return Response.json([branch]);
      }
      if (url.includes("/api/v1/customers/queue-requests") && method === "POST") {
        requests = [
          {
            ...customerRequest,
            request_text: JSON.parse(String(init?.body)).request_text,
          },
        ];
        return Response.json(requests[0], { status: 201 });
      }
      if (url.includes("/api/v1/customers/queue-requests")) {
        return Response.json(requests);
      }
      throw new Error(`Unexpected request: ${method} ${url}`);
    },
  );

  renderWithProviders(<MyQueueRequestsPanel />);
  const branchSelect = await screen.findByLabelText("Branch");
  await screen.findByRole("option", { name: "Main branch" });
  fireEvent.change(branchSelect, {
    target: { value: "branch-1" },
  });
  fireEvent.change(screen.getByLabelText("What do you need?"), {
    target: { value: "I need help with a general account issue." },
  });
  const submitButton = screen.getByRole("button", { name: "Send request" });
  await waitFor(() => expect(submitButton).toBeEnabled());
  fireEvent.click(submitButton);

  expect(await screen.findByText(/service team will assign your request/i)).toBeInTheDocument();
  expect(screen.getByText("I need help with a general account issue.")).toBeInTheDocument();
  expect(screen.getByText("pending")).toBeInTheDocument();
  const submission = fetchMock.mock.calls.find(
    ([input, init]) =>
      String(input).includes("/api/v1/customers/queue-requests") &&
      init?.method === "POST",
  );
  expect(JSON.parse(String(submission?.[1]?.body))).toEqual({
    branch_id: "branch-1",
    request_text: "I need help with a general account issue.",
  });
});

it("lets staff or admins assign an open queue and approve a request", async () => {
  useAuthStore.setState({
    token: "staff-token",
    user: {
      id: "staff-1",
      full_name: "Branch Staff",
      email: "staff@example.test",
      role: "staff",
      organization_id: "org-1",
      branch_id: "branch-1",
      created_at: new Date().toISOString(),
    },
    ready: true,
  });
  let reviewItems: QueueRequest[] = [customerRequest];
  let approvedItems: QueueRequest[] = [];
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(
    async (input, init) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.includes("/api/v1/queue-requests/review")) {
        const items = url.includes("status=reviewed") ? approvedItems : reviewItems;
        return Response.json({
          items,
          total: items.length,
          pending_total: reviewItems.length,
          page: 1,
          page_size: 50,
        });
      }
      if (url.includes("/api/v1/queue-requests/request-1/approve")) {
        expect(JSON.parse(String(init?.body))).toEqual({ queue_id: "queue-1" });
        approvedItems = [
          {
            ...customerRequest,
            status: "approved",
            assigned_queue_id: "queue-1",
            assigned_queue_name: "General help",
            queue_entry_id: "ticket-1",
            queue_number: 1,
            queue_prefix: "G",
          },
        ];
        reviewItems = [];
        return Response.json(approvedItems[0]);
      }
      throw new Error(`Unexpected request: ${method} ${url}`);
    },
  );

  renderWithProviders(
    <QueueRequestReviewPanel
      queues={[{ id: "queue-1", name: "General help", status: "open" }]}
    />,
  );
  fireEvent.change(await screen.findByLabelText("Assign to queue"), {
    target: { value: "queue-1" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Approve and issue ticket" }));

  await waitFor(() =>
    expect(screen.getByText("No pending requests for review.")).toBeInTheDocument(),
  );
  await waitFor(() =>
    expect(
      fetchMock.mock.calls.some(([input]) =>
        String(input).includes("status=reviewed"),
      ),
    ).toBe(true),
  );
  expect(await screen.findByText("Recently reviewed")).toBeInTheDocument();
  expect(screen.getByText("Ticket issued in General help · G1")).toBeInTheDocument();
  expect(
    fetchMock.mock.calls.some(([input]) =>
      String(input).includes("/api/v1/queue-requests/request-1/approve"),
    ),
  ).toBe(true);
});
