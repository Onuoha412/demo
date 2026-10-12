import { apiRequest, resolveApiBaseUrl } from "../services/api";
import { login } from "../services/auth";
import { getQueueEntry, getServices, joinService } from "../services/queue";
import { verifyAdminQueueEntry } from "../services/admin";
import { useAuthStore } from "../store/authStore";

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  useAuthStore.setState({ token: null, user: null, ready: true });
  vi.restoreAllMocks();
});

function mockResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

it("customer can authenticate", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
    mockResponse({
      session_token: "customer-session-token",
      user: {
        id: "u1",
        full_name: "Customer",
        email: "customer@example.com",
        role: "customer",
        organization_id: null,
        created_at: new Date().toISOString(),
      },
    }),
  );
  const auth = await login({ email: "customer@example.com", password: "password123" });
  expect(auth.user.email).toBe("customer@example.com");
  expect(auth.session_token).toBe("customer-session-token");
  expect(fetch).toHaveBeenCalledWith(
    expect.stringContaining("/api/v1/auth/login"),
    expect.objectContaining({ credentials: "omit" }),
  );
});

it("customer can retrieve services", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
    mockResponse([
      {
        id: "svc-1",
        branch_id: "branch-1",
        name: "Admissions",
        code: "ADM",
        description: null,
        average_service_minutes: 10,
        queue_id: "queue-1",
      },
    ]),
  );
  const services = await getServices();
  expect(services[0].name).toBe("Admissions");
});

it("uses the local backend for production previews served on localhost", () => {
  expect(resolveApiBaseUrl(undefined, false, "localhost")).toBe(
    "http://localhost:8000",
  );
  expect(resolveApiBaseUrl("https://api.example.com/", false, "localhost")).toBe(
    "https://api.example.com",
  );
  expect(resolveApiBaseUrl(undefined, true, "localhost")).toBe("");
  expect(resolveApiBaseUrl(undefined, false, "queueless.example.com")).toBe("");
});

it("does not send a JSON content type on public GET requests", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
    mockResponse([]),
  );

  await getServices();

  const requestHeaders = new Headers(fetchMock.mock.calls[0][1]?.headers);
  expect(requestHeaders.has("Content-Type")).toBe(false);
});

it("explains when an API request receives an HTML error response", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
    new Response("<!doctype html><title>Not found</title>", {
      status: 404,
      headers: { "Content-Type": "text/html" },
    }),
  );

  await expect(apiRequest("/api/v1/catalog/services")).rejects.toMatchObject({
    name: "ApiError",
    status: 404,
    detail: "API endpoint not found. Check that the frontend is connected to the QueueLess backend.",
  });
});

it("shows backend validation detail for failed registration and login requests", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
    mockResponse({ detail: [{ loc: ["body", "email"], msg: "Invalid email" }] }, 422),
  );

  await expect(
    apiRequest("/api/v1/auth/register", { method: "POST", body: "{}" }),
  ).rejects.toMatchObject({ detail: "body.email: Invalid email" });
});

it("customer can join queue", async () => {
  sessionStorage.setItem("queueless.session", "token-1");
  localStorage.setItem(
    "queueless.user",
    JSON.stringify({
      id: "u1",
      full_name: "Customer",
      email: "customer@example.com",
      role: "customer",
      organization_id: null,
      created_at: new Date().toISOString(),
    }),
  );
  useAuthStore.setState({
    token: "token-1",
    user: { id: "u1", full_name: "Customer", email: "customer@example.com", role: "customer", organization_id: null, created_at: new Date().toISOString() },
  });
  vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
    mockResponse(
      {
        id: "entry-1",
        queue_prefix: "A",
        queue_number: 10,
        status: "waiting",
        people_ahead: 2,
        estimated_wait_minutes: 20,
        counter_id: null,
        counter: null,
        joined_at: new Date().toISOString(),
        called_at: null,
        service_started_at: null,
        completed_at: null,
      },
      201,
    ),
  );
  const entry = await joinService("svc-1", "branch-1", "  Need assistance  ");
  expect(entry.queue_number).toBe(10);
  expect(fetch).toHaveBeenCalledWith(
    expect.stringContaining("/customers/services/svc-1/join"),
    expect.objectContaining({
      credentials: "omit",
      body: JSON.stringify({ request_note: "Need assistance" }),
    }),
  );
  const requestHeaders = new Headers(vi.mocked(fetch).mock.calls[0][1]?.headers);
  expect(requestHeaders.get("authorization")).toBe("Bearer token-1");
});

it("customer can retrieve queue position", async () => {
  sessionStorage.setItem("queueless.session", "token-1");
  localStorage.setItem(
    "queueless.user",
    JSON.stringify({
      id: "u1",
      full_name: "Customer",
      email: "customer@example.com",
      role: "customer",
      organization_id: null,
      created_at: new Date().toISOString(),
    }),
  );
  useAuthStore.setState({
    token: "token-1",
    user: { id: "u1", full_name: "Customer", email: "customer@example.com", role: "customer", organization_id: null, created_at: new Date().toISOString() },
  });
  vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
    mockResponse({
      id: "entry-1",
      queue_prefix: "A",
      queue_number: 10,
      status: "called",
      people_ahead: 0,
      estimated_wait_minutes: 0,
      counter_id: "counter-1",
      counter: { id: "counter-1", name: "Counter 1", number: 1, status: "available" },
      joined_at: new Date().toISOString(),
      called_at: new Date().toISOString(),
      service_started_at: null,
      completed_at: null,
    }),
  );
  const entry = await getQueueEntry("entry-1");
  expect(entry.status).toBe("called");
  expect(entry.counter?.name).toBe("Counter 1");
});

it("administrator can verify a queue request", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
    mockResponse({
      id: "entry-1",
      request_note: "Need assistance",
      verified_at: new Date().toISOString(),
      verified_by_user_id: "admin-1",
    }),
  );

  const result = await verifyAdminQueueEntry("entry-1", "admin-session");

  expect(result).toMatchObject({
    id: "entry-1",
    request_note: "Need assistance",
    verified_by_user_id: "admin-1",
  });
  expect(fetch).toHaveBeenCalledWith(
    expect.stringContaining("/api/v1/admin/queue-entries/entry-1/verify"),
    expect.objectContaining({
      method: "POST",
      credentials: "omit",
    }),
  );
});
