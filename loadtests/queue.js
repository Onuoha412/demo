import http from "k6/http";
import { check, sleep } from "k6";

const baseUrl = __ENV.BASE_URL?.replace(/\/$/, "");
const serviceId = __ENV.SERVICE_ID;
const queueId = __ENV.QUEUE_ID;
const vus = Number(__ENV.VUS || 5);
const duration = __ENV.DURATION || "30s";

export const options = {
  vus,
  duration,
  thresholds: {
    checks: ["rate>0.95"],
  },
};

export function setup() {
  if (!baseUrl || !serviceId || !queueId || !__ENV.LOAD_TEST_PASSWORD) {
    throw new Error(
      "Set BASE_URL, SERVICE_ID, QUEUE_ID, and LOAD_TEST_PASSWORD for an isolated test deployment.",
    );
  }

  const tokens = [];
  const runId = `${Date.now()}-${Math.floor(Math.random() * 1_000_000)}`;
  for (let vu = 0; vu < vus; vu += 1) {
    const response = http.post(
      `${baseUrl}/api/v1/auth/register`,
      JSON.stringify({
        full_name: "QueueLess Load Test",
        email: `load-${runId}-${vu}@example.invalid`,
        password: __ENV.LOAD_TEST_PASSWORD,
      }),
      { headers: { "Content-Type": "application/json" } },
    );
    const registered = check(response, {
      "load-test customer registration succeeds": (result) =>
        result.status === 201,
    });
    if (!registered) {
      throw new Error("Unable to create a load-test customer.");
    }
    tokens.push(response.json("access_token"));
  }
  return { tokens };
}

export default function (data) {
  const token = data.tokens[(__VU - 1) % data.tokens.length];
  const headers = { Authorization: `Bearer ${token}` };
  const joined = http.post(
    `${baseUrl}/api/v1/customers/services/${serviceId}/join`,
    null,
    { headers },
  );
  check(joined, {
    "queue join succeeds": (response) => response.status === 201,
    "queue number is positive": (response) =>
      response.status === 201 && Number(response.json("queue_number")) > 0,
  });

  const status = http.get(
    `${baseUrl}/api/v1/queues/${queueId}?page=1&page_size=20`,
  );
  check(status, {
    "queue status succeeds": (response) => response.status === 200,
    "queue status returns paginated entries": (response) =>
      response.status === 200 &&
      response.json("entries") instanceof Array &&
      response.json("page_size") === 20,
  });
  sleep(1);
}
