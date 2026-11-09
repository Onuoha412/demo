import http from "k6/http";
import { Counter, Rate, Trend } from "k6/metrics";
import { check, sleep } from "k6";

const baseUrl = __ENV.BASE_URL?.replace(/\/$/, "");
const queueId = __ENV.QUEUE_ID;
const profiles = {
  A: { registeredUsers: 100, activeUsers: 20 },
  B: { registeredUsers: 400, activeUsers: 100 },
  C: { registeredUsers: 780, activeUsers: 200 },
  D: { registeredUsers: 780, activeUsers: 780 },
  E: { registeredUsers: 750, activeUsers: 750 },
};
const profileName = (__ENV.PROFILE || "A").toUpperCase();
const profile = profiles[profileName];
if (!profile) {
  throw new Error("PROFILE must be A, B, C, D, or E.");
}
const registeredUsers = Number(
  __ENV.REGISTERED_USERS || profile.registeredUsers,
);
const vus = Number(__ENV.VUS || profile.activeUsers);
const duration = __ENV.DURATION || "30s";
const joinLatency = new Trend("queue_join_latency", true);
const queueReadLatency = new Trend("queue_read_latency", true);
const databaseContention = new Counter("database_lock_errors");
const failedRequests = new Rate("failed_requests");

export const options = {
  vus,
  duration,
  thresholds: {
    checks: ["rate>0.95"],
    failed_requests: ["rate<0.05"],
    queue_join_latency: ["p(95)<2000"],
    queue_read_latency: ["p(95)<2000"],
  },
};

export function setup() {
  if (
    !baseUrl ||
    !queueId ||
    !__ENV.LOAD_TEST_PASSWORD ||
    __ENV.ISOLATED_TEST_TARGET !== "YES"
  ) {
    throw new Error(
      "Set BASE_URL, QUEUE_ID, LOAD_TEST_PASSWORD, and ISOLATED_TEST_TARGET=YES for an isolated test deployment.",
    );
  }
  if (
    !Number.isInteger(registeredUsers) ||
    !Number.isInteger(vus) ||
    registeredUsers < 1 ||
    vus < 1 ||
    registeredUsers < vus
  ) {
    throw new Error(
      "Registered users and VUs must be positive integers, with users >= VUs.",
    );
  }

  const tokens = [];
  const runId = `${Date.now()}-${Math.floor(Math.random() * 1_000_000)}`;
  const registrationUrl = `${baseUrl}/api/v1/auth/register`;
  const registrationParams = {
    headers: { "Content-Type": "application/json" },
  };
  for (let offset = 0; offset < registeredUsers; offset += 20) {
    const batchSize = Math.min(20, registeredUsers - offset);
    const requests = Array.from({ length: batchSize }, (_, index) => ({
      method: "POST",
      url: registrationUrl,
      body: JSON.stringify({
        full_name: "QueueLess Load Test",
        email: `load-${runId}-${offset + index}@example.invalid`,
        password: __ENV.LOAD_TEST_PASSWORD,
      }),
      params: registrationParams,
    }));
    const responses = http.batch(requests);
    responses.forEach((response, index) => {
      const registered = check(response, {
        "load-test customer registration succeeds": (result) =>
          result.status === 201,
      });
      if (!registered) {
        throw new Error(
          `Unable to create load-test customer ${offset + index}.`,
        );
      }
      tokens.push(response.json("session_token"));
    });
  }
  if (tokens.some((token) => typeof token !== "string" || token.length === 0)) {
    throw new Error(
      "Registration did not return a session token for every test user.",
    );
  }
  console.log(
    `Starting profile ${profileName}: ${registeredUsers} registered users, ${vus} active VUs.`,
  );
  return { tokens };
}

export default function (data) {
  const token = data.tokens[(__VU - 1) % data.tokens.length];
  const headers = { Authorization: `Bearer ${token}` };
  const joined = http.post(
    `${baseUrl}/api/v1/queues/${queueId}/join`,
    null,
    { headers },
  );
  joinLatency.add(joined.timings.duration);
  if (joined.status === 503 || joined.status === 504) {
    databaseContention.add(1);
  }
  failedRequests.add(joined.status < 200 || joined.status >= 400);
  check(joined, {
    "queue join succeeds": (response) => response.status === 201,
    "queue number is positive": (response) =>
      response.status === 201 && Number(response.json("queue_number")) > 0,
  });

  const status = http.get(
    `${baseUrl}/api/v1/queues/${queueId}?page=1&page_size=20`,
    { headers },
  );
  queueReadLatency.add(status.timings.duration);
  if (status.status === 503 || status.status === 504) {
    databaseContention.add(1);
  }
  failedRequests.add(status.status < 200 || status.status >= 400);
  check(status, {
    "queue status succeeds": (response) => response.status === 200,
    "queue status returns paginated entries": (response) =>
      response.status === 200 &&
      response.json("entries") instanceof Array &&
      response.json("page_size") === 20,
  });
  sleep(1);
}
