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
  sessionStorage.clear();
  useAuthStore.setState({ token: null, user: null, ready: true });
  vi.restoreAllMocks();
});

it("validates login form", async () => {
  setPath("/login");
  renderApp();
  fireEvent.change(await screen.findByLabelText(/^email/i), { target: { value: "valid@email.com" } });
  fireEvent.change(await screen.findByLabelText(/^password$/i), { target: { value: "short" } });
  fireEvent.click(screen.getByRole("button", { name: /sign in/i }));
  expect(await screen.findByText(/at least 8 characters/i)).toBeInTheDocument();
});

it("validates register form", async () => {
  setPath("/register");
  renderApp();
  fireEvent.change(await screen.findByLabelText(/full name/i), { target: { value: "A" } });
  fireEvent.change(await screen.findByLabelText(/^email$/i), { target: { value: "bad" } });
  fireEvent.change(await screen.findByLabelText(/^password$/i), { target: { value: "123" } });
  fireEvent.click(screen.getByRole("button", { name: /create account/i }));
  expect(await screen.findByText(/full name/i)).toBeInTheDocument();
});

it("sends a newly registered customer to the service list", async () => {
  setPath("/register");
  mockFetchSequence([
    { body: { client_id: "google-client-id", nonce: "test-google-nonce" } },
    {
      body: [{ id: "org-1", name: "Organization", slug: "organization", description: null }],
    },
    {
      status: 201,
      body: {
        session_token: "new-customer-session",
        user: {
          id: "customer-1",
          full_name: "New Customer",
          email: "new@example.com",
          role: "customer",
          organization_id: null,
          created_at: new Date().toISOString(),
        },
      },
    },
    {
      body: [
        {
          id: "org-1",
          name: "Organization",
          slug: "organization",
          description: null,
        },
      ],
    },
    {
      body: [
        {
          id: "branch-1",
          organization_id: "org-1",
          name: "Main",
          address: null,
          timezone: "UTC",
        },
      ],
    },
    {
      body: [
        {
          id: "service-1",
          branch_id: "branch-1",
          name: "Admissions",
          code: "ADM",
          description: null,
          average_service_minutes: 10,
          queue_id: "queue-1",
        },
      ],
    },
  ]);
  renderApp();

  fireEvent.change(await screen.findByLabelText(/full name/i), {
    target: { value: "New Customer" },
  });
  fireEvent.change(await screen.findByLabelText(/^email$/i), {
    target: { value: "new@example.com" },
  });
  fireEvent.change(await screen.findByLabelText(/^password$/i), {
    target: { value: "customer-password" },
  });
  fireEvent.change(await screen.findByLabelText(/confirm password/i), {
    target: { value: "customer-password" },
  });
  fireEvent.click(await screen.findByRole("button", { name: /create account/i }));

  await waitFor(() => expect(window.location.pathname).toBe("/services"));
  expect(await screen.findByText("Admissions")).toBeInTheDocument();
});

it("signs in a customer and stores the tab-scoped session", async () => {
  setPath("/login");
  mockFetchSequence([
    { body: { client_id: "google-client-id", nonce: "test-google-nonce" } },
    {
      body: {
        session_token: "login-session",
        user: {
          id: "customer-1",
          full_name: "Returning Customer",
          email: "returning@example.com",
          role: "customer",
          organization_id: null,
          branch_id: null,
          created_at: new Date().toISOString(),
        },
      },
    },
    { body: [] },
  ]);
  renderApp();

  fireEvent.change(await screen.findByLabelText(/^email/i), {
    target: { value: "returning@example.com" },
  });
  fireEvent.change(await screen.findByLabelText(/^password$/i), {
    target: { value: "customer-password" },
  });
  fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

  expect(
    await screen.findByRole("heading", { name: "Your time is yours again." }),
  ).toBeInTheDocument();
  expect(sessionStorage.getItem("queueless.session")).toBe("login-session");
});

it("keeps unauthenticated users out of admin routes", async () => {
  setPath("/admin/dashboard");
  renderApp();
  await waitFor(() => expect(window.location.pathname).toBe("/admin/login"));
  expect(await screen.findByRole("heading", { name: /administrator sign in/i })).toBeInTheDocument();
});

it("keeps non-staff users out of staff routes", async () => {
  setPath("/staff/dashboard");
  renderApp();
  await waitFor(() => expect(window.location.pathname).toBe("/staff/login"));
});

it("routes staff to the staff interface from the app home", async () => {
  useAuthStore.setState({
    token: "staff-token",
    user: {
      id: "staff-1",
      full_name: "Staff User",
      email: "staff@example.com",
      role: "staff",
      organization_id: null,
      created_at: new Date().toISOString(),
    },
  });
  setPath("/");
  renderApp();
  await waitFor(() => expect(window.location.pathname).toBe("/staff/dashboard"));
  expect(screen.getByRole("link", { name: "Dashboard" })).toHaveAttribute(
    "href",
    "/staff/dashboard",
  );
});

it("keeps customers on the customer home instead of redirecting to itself", async () => {
  useAuthStore.setState({
    token: "customer-token",
    user: {
      id: "customer-1",
      full_name: "Customer User",
      email: "customer@example.com",
      role: "customer",
      organization_id: null,
      created_at: new Date().toISOString(),
    },
  });
  setPath("/");
  mockFetchSequence([
    {
      body: [
        {
          id: "service-1",
          branch_id: "branch-1",
          name: "Passport services",
          code: "PASS",
          description: "Apply or renew a passport.",
          average_service_minutes: 12,
          queue_id: "queue-1",
        },
      ],
    },
  ]);
  renderApp();

  expect(
    await screen.findByRole("heading", { name: "Your time is yours again." }),
  ).toBeInTheDocument();
  expect(
    await screen.findByRole("heading", { name: "Passport services" }),
  ).toBeInTheDocument();
  expect(window.location.pathname).toBe("/");
});

it("routes administrators to the admin interface from the app home", async () => {
  useAuthStore.setState({
    token: "admin-token",
    user: {
      id: "admin-1",
      full_name: "Admin User",
      email: "admin@example.com",
      role: "admin",
      organization_id: null,
      created_at: new Date().toISOString(),
    },
  });
  setPath("/");
  renderApp();
  await waitFor(() => expect(window.location.pathname).toBe("/admin/dashboard"));
  expect(screen.getByRole("link", { name: "Manage" })).toHaveAttribute(
    "href",
    "/admin/organizations",
  );
});

it("opens the requested admin resource page", async () => {
  useAuthStore.setState({
    token: "admin-token",
    user: {
      id: "admin-1",
      full_name: "Admin User",
      email: "admin@example.com",
      role: "admin",
      organization_id: null,
      created_at: new Date().toISOString(),
    },
  });
  setPath("/admin/services");
  mockFetchSequence([
    {
      body: {
        items: [],
        total: 0,
        page: 1,
        page_size: 20,
      },
    },
  ]);

  renderApp();

  expect(
    await screen.findByRole("heading", { name: "Services" }, { timeout: 5_000 }),
  ).toBeInTheDocument();
  expect(screen.getByText("Create")).toBeInTheDocument();
});

it("keeps staff accounts out of customer-only routes", async () => {
  useAuthStore.setState({
    token: "staff-token",
    user: {
      id: "staff-1",
      full_name: "Staff User",
      email: "staff@example.com",
      role: "staff",
      organization_id: null,
      created_at: new Date().toISOString(),
    },
  });
  setPath("/history");
  renderApp();
  await waitFor(() => expect(window.location.pathname).toBe("/staff/dashboard"));
});

it("renders the service loading and error states", async () => {
  setPath("/services");
  const fetchMock = vi.spyOn(globalThis, "fetch");
  let rejectRequest!: (error: Error) => void;
  fetchMock.mockReturnValueOnce(new Promise<Response>((_resolve, reject) => { rejectRequest = reject; }));
  renderApp();
  expect(await screen.findByText("Loading services...")).toBeInTheDocument();
  rejectRequest(new Error("offline"));
  expect(await screen.findByText(/cannot reach the queueless api/i)).toBeInTheDocument();
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
        queue_prefix: "A",
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
        request_note: "Need help with my application.",
        verified_at: null,
      },
    },
    {
      body: {
        id: "entry-1",
        queue_prefix: "A",
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
        request_note: "Need help with my application.",
        verified_at: null,
      },
    },
  ]);
  renderApp();
  const joinButton = await screen.findByRole("button", { name: /confirm and join/i });
  await waitFor(() => expect(joinButton).toBeEnabled());
  fireEvent.change(screen.getByLabelText(/request details/i), {
    target: { value: "Need help with my application." },
  });
  fireEvent.click(joinButton);
  expect(await screen.findByText("Your queue ticket")).toBeInTheDocument();
  expect(await screen.findByText("A012")).toBeInTheDocument();
  expect(await screen.findByText("Your request: Need help with my application.")).toBeInTheDocument();
  expect(await screen.findByText("Request awaiting verification")).toBeInTheDocument();
  expect(await screen.findByText("Counter 1")).toBeInTheDocument();
  expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/customers/services/svc-1/join?branch_id=branch-1"))).toBe(true);
  const joinRequest = fetchMock.mock.calls.find(([url]) =>
    String(url).includes("/customers/services/svc-1/join?branch_id=branch-1"),
  );
  expect(JSON.parse(String(joinRequest?.[1]?.body))).toEqual({
    request_note: "Need help with my application.",
  });
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
  await waitFor(() => expect(screen.getByRole("heading", { name: /welcome back/i })).toBeInTheDocument());
});
