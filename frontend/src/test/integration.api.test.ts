import { login } from "../services/auth";
import { getQueueEntry, getServices, joinService } from "../services/queue";
import { useAuthStore } from "../store/authStore";

beforeEach(() => {
  localStorage.clear();
  useAuthStore.setState({ token: null, user: null });
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
      access_token: "token-1",
      token_type: "bearer",
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
  expect(auth.access_token).toBe("token-1");
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

it("customer can join queue", async () => {
  localStorage.setItem("queueless.token", "token-1");
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
  const entry = await joinService("svc-1");
  expect(entry.queue_number).toBe(10);
});

it("customer can retrieve queue position", async () => {
  localStorage.setItem("queueless.token", "token-1");
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
