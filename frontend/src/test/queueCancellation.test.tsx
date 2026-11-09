import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { QueuePage } from "../pages/customer/QueuePage";
import { useAuthStore } from "../store/authStore";

vi.mock("../hooks/useQueueWebSocket", () => ({
  useQueueWebSocket: () => ({ event: null, status: "connected" }),
}));

vi.mock("../hooks/useBrowserNotifications", () => ({
  useBrowserNotifications: () => vi.fn(),
}));

beforeEach(() => {
  vi.restoreAllMocks();
  useAuthStore.setState({
    token: "customer-session",
    ready: true,
    user: {
      id: "customer-1",
      full_name: "Sample Customer",
      email: "sample@example.test",
      role: "customer",
      organization_id: null,
      created_at: new Date().toISOString(),
    },
  });
});

it("cancels a waiting ticket and reloads its authoritative status", async () => {
  let status = "waiting";
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    if (url.includes("/api/v1/customers/queue-entries/entry-1")) {
      return Response.json({
        id: "entry-1",
        queue_id: "queue-1",
        queue_prefix: "A",
        queue_number: 7,
        status,
        people_ahead: 2,
        estimated_wait_minutes: 20,
        counter_id: null,
        counter: null,
        joined_at: new Date().toISOString(),
        called_at: null,
        service_started_at: null,
        completed_at: null,
        request_note: null,
        verified_at: null,
        verified_by_user_id: null,
        transferred_to_entry_id: null,
      });
    }
    if (url.includes("/api/v1/ai/wait-time/entry-1")) {
      return Response.json({
        estimated_minutes: 20,
        lower_bound_minutes: 15,
        upper_bound_minutes: 25,
        confidence: 0.7,
        model_version: "test",
        factors: {
          people_ahead: 2,
          queue_length: 3,
          average_service_duration: 10,
          active_counters: 1,
          historical_samples: 0,
          service_type: "general",
          hour_of_day: 9,
          day_of_week: 1,
          current_processing_rate: 1,
          explanation: "Queue estimate",
        },
      });
    }
    if (url.includes("/api/v1/queue-entries/entry-1/cancel")) {
      expect(init?.method).toBe("POST");
      status = "cancelled";
      return Response.json({ id: "entry-1", status });
    }
    throw new Error(`Unexpected request: ${url}`);
  });
  vi.stubGlobal("confirm", vi.fn(() => true));
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/queue/entry-1"]}>
        <Routes>
          <Route path="/queue/:entryId" element={<QueuePage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );

  fireEvent.click(
    await screen.findByRole("button", { name: "Cancel my place" }),
  );

  expect(await screen.findByRole("status")).toHaveTextContent(
    "Your place in the queue has been cancelled.",
  );
  await waitFor(() => expect(screen.getByText("Status: CANCELLED")).toBeInTheDocument());
  expect(screen.queryByRole("button", { name: "Cancel my place" })).not.toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining("/api/v1/queue-entries/entry-1/cancel"),
    expect.objectContaining({ method: "POST" }),
  );
  expect(window.confirm).toHaveBeenCalledOnce();
});
