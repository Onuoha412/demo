import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { AppointmentsPage } from "../pages/customer/AppointmentsPage";
import { useAuthStore } from "../store/authStore";

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

it("books an available appointment and checks in within the allowed window", async () => {
  const startsAt = new Date(Date.now() + 5 * 60_000).toISOString();
  const endsAt = new Date(Date.now() + 35 * 60_000).toISOString();
  let appointmentStatus: "booked" | "checked_in" | null = null;
  const appointment = () => ({
    id: "appointment-1",
    slot_id: "slot-1",
    service_id: "service-1",
    service_name: "Consultation",
    starts_at: startsAt,
    ends_at: endsAt,
    status: appointmentStatus ?? "booked",
    checked_in_at:
      appointmentStatus === "checked_in" ? new Date().toISOString() : null,
    created_at: new Date().toISOString(),
  });

  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(
    async (input, init) => {
      const url = new URL(String(input), window.location.origin);
      if (
        url.pathname.endsWith("/api/v1/customers/appointments") &&
        init?.method !== "POST"
      ) {
        return Response.json(appointmentStatus ? [appointment()] : []);
      }
      if (url.pathname.endsWith("/api/v1/customers/appointment-slots")) {
        return Response.json(
          appointmentStatus
            ? []
            : [
                {
                  id: "slot-1",
                  service_id: "service-1",
                  starts_at: startsAt,
                  ends_at: endsAt,
                  capacity: 1,
                  booked_count: 0,
                  is_open: true,
                },
              ],
        );
      }
      if (
        url.pathname.endsWith("/api/v1/customers/appointments") &&
        init?.method === "POST"
      ) {
        appointmentStatus = "booked";
        return Response.json(appointment(), { status: 201 });
      }
      if (url.pathname.endsWith("/api/v1/customers/appointments/appointment-1/check-in")) {
        appointmentStatus = "checked_in";
        return Response.json(appointment());
      }
      throw new Error(`Unexpected request: ${url.pathname}`);
    },
  );
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/services/service-1/appointments"]}>
        <Routes>
          <Route
            path="/services/:serviceId/appointments"
            element={<AppointmentsPage />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );

  fireEvent.click(await screen.findByRole("button", { name: "Book this time" }));
  fireEvent.click(await screen.findByRole("button", { name: "Check in" }));
  expect(await screen.findByText(/checked in/)).toBeInTheDocument();
  expect(
    fetchMock.mock.calls.some(
      ([input, init]) =>
        String(input).endsWith("/api/v1/customers/appointments") &&
        init?.method === "POST",
    ),
  ).toBe(true);
  expect(
    fetchMock.mock.calls.some(
      ([input]) =>
        String(input).endsWith(
          "/api/v1/customers/appointments/appointment-1/check-in",
        ),
    ),
  ).toBe(true);
});
