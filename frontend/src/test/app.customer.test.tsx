import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import App from "../App";
import { useAuthStore } from "../store/authStore";

function setPath(path: string) {
  window.history.pushState({}, "", path);
}

function renderApp() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>,
  );
}

function mockFetchSequence(responses: Array<{ status?: number; body: unknown }>) {
  const fetchMock = vi.spyOn(globalThis, "fetch");
  for (const response of responses) {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify(response.body), {
        status: response.status ?? 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
  }
  return fetchMock;
}

beforeEach(() => {
  localStorage.clear();
  useAuthStore.setState({ token: null, user: null });
  vi.restoreAllMocks();
});

it("validates login form", async () => {
  setPath("/login");
  renderApp();
  fireEvent.change(screen.getByLabelText(/^email/i), { target: { value: "valid@email.com" } });
  fireEvent.change(screen.getByLabelText(/password/i), { target: { value: "short" } });
  fireEvent.click(screen.getByRole("button", { name: /sign in/i }));
  expect(await screen.findByText(/at least 8 characters/i)).toBeInTheDocument();
});

it("validates register form", async () => {
  setPath("/register");
  renderApp();
  fireEvent.change(screen.getByLabelText(/full name/i), { target: { value: "A" } });
  fireEvent.change(screen.getByLabelText(/^email/i), { target: { value: "bad" } });
  fireEvent.change(screen.getByLabelText(/password/i), { target: { value: "123" } });
  fireEvent.click(screen.getByRole("button", { name: /create account/i }));
  expect(await screen.findByText(/full name/i)).toBeInTheDocument();
});

it("keeps unauthenticated users out of admin routes", async () => {
  setPath("/admin/dashboard");
  renderApp();
  await waitFor(() => expect(window.location.pathname).toBe("/admin/login"));
});

it("keeps non-staff users out of staff routes", async () => {
  setPath("/staff/dashboard");
  renderApp();
  await waitFor(() => expect(window.location.pathname).toBe("/staff/login"));
});

it("renders the service loading and error states", async () => {
  setPath("/services");
  const fetchMock = vi.spyOn(globalThis, "fetch");
  let rejectRequest!: (error: Error) => void;
  fetchMock.mockReturnValueOnce(new Promise<Response>((_resolve, reject) => { rejectRequest = reject; }));
  renderApp();
  expect(screen.getByText(/loading/i)).toBeInTheDocument();
  rejectRequest(new Error("offline"));
  expect(await screen.findByText(/network error/i)).toBeInTheDocument();
});

it("renders service list", async () => {
  setPath("/services");
  mockFetchSequence([
    { body: [{ id: "org-1", name: "Babcock University", slug: "babcock", description: null }] },
    { body: [{ id: "branch-1", organization_id: "org-1", name: "Student Affairs", address: null, timezone: "Africa/Lagos" }] },
    { body: [{ id: "svc-1", branch_id: "branch-1", name: "Admissions", code: "ADM", description: "Admissions desk", average_service_minutes: 10, queue_id: "q-1" }] },
  ]);
  renderApp();
  expect(await screen.findByText("Admissions")).toBeInTheDocument();
});

it("supports join queue flow and renders ticket + position", async () => {
  localStorage.setItem("queueless.token", "token");
  localStorage.setItem(
    "queueless.user",
    JSON.stringify({ id: "u1", full_name: "User", email: "a@b.com", role: "customer", organization_id: null, created_at: new Date().toISOString() }),
  );
  useAuthStore.setState({
    token: "token",
    user: { id: "u1", full_name: "User", email: "a@b.com", role: "customer", organization_id: null, created_at: new Date().toISOString() },
  });
  setPath("/join/branch-1/svc-1");
  const fetchMock = mockFetchSequence([
    { body: { id: "svc-1", branch_id: "branch-1", name: "Admissions", code: "ADM", description: null, average_service_minutes: 10, queue_id: "q1" } },
    {
      status: 201,
      body: {
        id: "entry-1",
        queue_number: 12,
        status: "waiting",
        people_ahead: 3,
        estimated_wait_minutes: 30,
        counter_id: null,
        counter: null,
        joined_at: new Date().toISOString(),
        called_at: null,
        service_started_at: null,
        completed_at: null,
      },
    },
    {
      body: {
        id: "entry-1",
        queue_number: 12,
        status: "called",
        people_ahead: 0,
        estimated_wait_minutes: 0,
        counter_id: "c1",
        counter: { id: "c1", name: "Counter 1", number: 1, status: "available" },
        joined_at: new Date().toISOString(),
        called_at: new Date().toISOString(),
        service_started_at: null,
        completed_at: null,
      },
    },
  ]);
  renderApp();
  const joinButton = await screen.findByRole("button", { name: /confirm and join/i });
  await waitFor(() => expect(joinButton).toBeEnabled());
  fireEvent.click(joinButton);
  expect(await screen.findByText("Your queue ticket")).toBeInTheDocument();
  expect(await screen.findByText("12")).toBeInTheDocument();
  expect(await screen.findByText("Counter 1")).toBeInTheDocument();
  expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/customers/services/svc-1/join?branch_id=branch-1"))).toBe(true);
});

it("renders history", async () => {
  localStorage.setItem("queueless.token", "token");
  localStorage.setItem(
    "queueless.user",
    JSON.stringify({ id: "u1", full_name: "User", email: "a@b.com", role: "customer", organization_id: null, created_at: new Date().toISOString() }),
  );
  useAuthStore.setState({
    token: "token",
    user: { id: "u1", full_name: "User", email: "a@b.com", role: "customer", organization_id: null, created_at: new Date().toISOString() },
  });
  setPath("/history");
  mockFetchSequence([
    {
      body: {
        page: 1,
        page_size: 50,
        total: 1,
        items: [
          {
            entry_id: "e1",
            queue_id: "q1",
            queue_name: "Admissions Queue",
            queue_prefix: "A",
            queue_number: 20,
            status: "completed",
            joined_at: new Date().toISOString(),
            completed_at: new Date().toISOString(),
          },
        ],
      },
    },
  ]);
  renderApp();
  expect(await screen.findByText("Admissions Queue")).toBeInTheDocument();
});

it("protects private routes", async () => {
  setPath("/history");
  renderApp();
  await waitFor(() => expect(screen.getByRole("heading", { name: /login/i })).toBeInTheDocument());
});
