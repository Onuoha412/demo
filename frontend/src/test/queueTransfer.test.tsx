import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { QueuePage } from "../pages/customer/QueuePage";
import { useAuthStore } from "../store/authStore";

vi.mock("../hooks/useQueueWebSocket", () => ({
  useQueueWebSocket: () => ({
    status: "connected",
    lastEventAt: null,
    event: undefined,
  }),
}));

beforeEach(() => {
  useAuthStore.setState({
    token: "customer-session",
    user: {
      id: "customer-1",
      full_name: "Customer",
      email: "customer@example.test",
      role: "customer",
      organization_id: null,
      created_at: new Date().toISOString(),
    },
    ready: true,
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

it("shows the customer a link to the replacement ticket after a transfer", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    Response.json({
      id: "entry-old",
      queue_id: "queue-source",
      queue_prefix: "A",
      queue_number: 12,
      status: "cancelled",
      people_ahead: 0,
      estimated_wait_minutes: 0,
      counter_id: null,
      counter: null,
      joined_at: new Date().toISOString(),
      called_at: null,
      service_started_at: null,
      completed_at: null,
      transferred_to_entry_id: "entry-new",
    }),
  );
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/queue/entry-old"]}>
        <Routes>
          <Route path="/queue/:entryId" element={<QueuePage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );

  const newTicketLink = await screen.findByRole("link", {
    name: "View your new ticket",
  });
  expect(newTicketLink).toHaveAttribute("href", "/queue/entry-new");
});
