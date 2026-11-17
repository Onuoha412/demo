import http from "k6/http";
import ws from "k6/ws";
import { check } from "k6";
import { Counter, Rate } from "k6/metrics";

const baseUrl = __ENV.BASE_URL?.replace(/\/$/, "");
const queueId = __ENV.QUEUE_ID;
const vus = Number(__ENV.VUS || 750);
const registeredUsers = Number(__ENV.REGISTERED_USERS || vus);
const holdMs = Number(__ENV.WS_HOLD_MS || 90_000);
const eventStartSeconds = 30;
const connectionSuccess = new Rate("websocket_connection_success");
const queueEventDelivery = new Rate("queue_event_delivery");
const failedRequests = new Rate("failed_requests");
const socketErrors = new Counter("websocket_errors");

export const options = {
  scenarios: {
    queue_websockets: {
      executor: "per-vu-iterations",
      vus,
      iterations: 1,
      maxDuration: `${Math.ceil(holdMs / 1000 + 30)}s`,
      exec: "openQueueSocket",
    },
    queue_event: {
      executor: "shared-iterations",
      vus: 1,
      iterations: 1,
      startTime: `${eventStartSeconds}s`,
      maxDuration: "30s",
      exec: "triggerQueueEvent",
    },
  },
  thresholds: {
    checks: ["rate>0.95"],
    failed_requests: ["rate<0.01"],
    websocket_connection_success: ["rate==1"],
    queue_event_delivery: ["rate>0.99"],
    ws_connecting: ["p(95)<5000"],
    ws_session_duration: [`p(95)>${holdMs - 5000}`],
    ws_sessions: [`count>=${vus}`],
  },
};

function authHeaders(token) {
  return {
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
  };
}

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
    !Number.isInteger(vus) ||
    !Number.isInteger(registeredUsers) ||
    vus < 1 ||
    registeredUsers < vus ||
    !Number.isInteger(holdMs) ||
    holdMs <= eventStartSeconds * 1000
  ) {
    throw new Error(
      "VUS and REGISTERED_USERS must be positive integers with users >= VUS; WS_HOLD_MS must exceed 30000.",
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
        full_name: "QueueLess WebSocket Load Test",
        email: `ws-load-${runId}-${offset + index}@example.invalid`,
        password: __ENV.LOAD_TEST_PASSWORD,
      }),
      params: registrationParams,
    }));
    const responses = http.batch(requests);
    responses.forEach((response, index) => {
      const registered = check(response, {
        "WebSocket load-test customer registration succeeds": (result) =>
          result.status === 201,
      });
      if (!registered) {
        throw new Error(
          `Unable to create WebSocket load-test customer ${offset + index}.`,
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
    `Starting authenticated WebSocket test: ${vus} concurrent clients for ${holdMs}ms.`,
  );
  return { tokens };
}

export function openQueueSocket(data) {
  const token = data.tokens[__VU - 1];
  const ticketResponse = http.post(
    `${baseUrl}/api/v1/auth/ws-ticket`,
    JSON.stringify({ queue_id: queueId }),
    authHeaders(token),
  );
  const ticketCreated = check(ticketResponse, {
    "WebSocket ticket is issued": (response) => response.status === 200,
  });
  failedRequests.add(!ticketCreated);
  if (!ticketCreated) {
    connectionSuccess.add(false);
    queueEventDelivery.add(false);
    return;
  }

  const ticket = ticketResponse.json("ticket");
  const wsUrl = `${baseUrl.replace(/^http/, "ws")}/ws/queues/${queueId}?ticket=${encodeURIComponent(ticket)}`;
  let receivedQueueEvent = false;
  const response = ws.connect(wsUrl, {}, (socket) => {
    socket.on("message", (rawMessage) => {
      try {
        const message = JSON.parse(rawMessage);
        if (message.event === "CUSTOMER_JOINED") {
          receivedQueueEvent = true;
        }
      } catch {
        socketErrors.add(1);
      }
    });
    socket.on("error", () => socketErrors.add(1));
    socket.setInterval(() => socket.send("ping"), 25_000);
    socket.setTimeout(() => socket.close(), holdMs);
  });

  const connected = check(response, {
    "WebSocket upgrade succeeds": (result) => result && result.status === 101,
  });
  const eventDelivered = check({ receivedQueueEvent }, {
    "queue update reaches connected WebSocket": (result) =>
      result.receivedQueueEvent,
  });
  connectionSuccess.add(connected);
  queueEventDelivery.add(connected && eventDelivered);
}

export function triggerQueueEvent(data) {
  const response = http.post(
    `${baseUrl}/api/v1/queues/${queueId}/join`,
    null,
    authHeaders(data.tokens[0]),
  );
  const joined = check(response, {
    "queue event trigger succeeds": (result) => result.status === 201,
  });
  failedRequests.add(!joined);
}
