import type { Event as SentryEvent } from "@sentry/react";

const apiUrl = import.meta.env.VITE_API_URL;
const sentryDsn = import.meta.env.VITE_SENTRY_DSN;
const posthogKey = import.meta.env.VITE_POSTHOG_KEY;
const posthogHost = import.meta.env.VITE_POSTHOG_HOST || "https://us.i.posthog.com";
type SentryModule = typeof import("@sentry/react");
type PostHogClient = typeof import("posthog-js").default;
let sentry: SentryModule | undefined;
let posthog: PostHogClient | undefined;
let sentryReady: Promise<void> | undefined;
let posthogReady: Promise<void> | undefined;
const uuidPathSegment =
  /(?<![0-9a-f])[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}(?![0-9a-f])/gi;

function safeUrl(value: string): string {
  try {
    const url = new URL(value, window.location.origin);
    url.pathname = url.pathname.replace(uuidPathSegment, ":id");
    url.search = "";
    url.hash = "";
    url.username = "";
    url.password = "";
    return url.toString();
  } catch {
    return "";
  }
}

function sanitizeSentryEvent<T extends SentryEvent>(event: T): T {
  delete event.user;
  delete event.extra;
  if (event.transaction) {
    event.transaction = event.transaction.replace(uuidPathSegment, ":id");
  }
  if (event.request) {
    if (event.request.url) event.request.url = safeUrl(event.request.url);
    delete event.request.data;
    delete event.request.cookies;
    delete event.request.query_string;
    delete event.request.env;
    if (event.request.headers) {
      for (const name of Object.keys(event.request.headers)) {
        if (["authorization", "cookie", "set-cookie", "referer"].includes(name.toLowerCase())) {
          delete event.request.headers[name];
        }
      }
    }
  }
  for (const span of event.spans ?? []) {
    for (const [name, value] of Object.entries(span.data ?? {})) {
      if (
        [
          "authorization",
          "cookie",
          "set-cookie",
          "http.query",
          "http.request.body",
          "http.request.headers",
          "db.statement",
          "db.params",
        ].includes(name.toLowerCase())
      ) {
        delete span.data?.[name];
      } else if (
        ["url", "http.url", "url.full"].includes(name.toLowerCase()) &&
        typeof value === "string"
      ) {
        span.data![name] = safeUrl(value);
      }
    }
  }
  for (const breadcrumb of event.breadcrumbs ?? []) {
    const data = breadcrumb.data;
    if (!data) continue;
    delete data.data;
    for (const name of Object.keys(data)) {
      if (["authorization", "cookie", "set-cookie"].includes(name.toLowerCase())) {
        delete data[name];
      }
    }
    for (const name of ["url", "from", "to"]) {
      if (typeof data[name] === "string") data[name] = safeUrl(data[name]);
    }
  }
  return event;
}

if (sentryDsn) {
  sentryReady = import("@sentry/react")
    .then((module) => {
      sentry = module;
      module.init({
        dsn: sentryDsn,
        tracesSampleRate: 0.05,
        integrations: [module.browserTracingIntegration()],
        tracePropagationTargets: apiUrl ? [new URL(apiUrl).origin] : [],
        beforeSend: sanitizeSentryEvent,
        beforeSendTransaction: sanitizeSentryEvent,
      });
    })
    .catch((error: unknown) => {
      console.error("Unable to initialize Sentry.", error);
    });
}

if (posthogKey) {
  posthogReady = import("posthog-js")
    .then(({ default: client }) => {
      posthog = client;
      client.init(posthogKey, {
        api_host: posthogHost,
        autocapture: false,
        capture_pageview: false,
        capture_pageleave: false,
        ip: false,
        save_referrer: false,
        save_campaign_params: false,
        get_current_url: () => "",
        property_denylist: [
          "$current_url",
          "$pathname",
          "$url",
          "$referrer",
          "$initial_referrer",
          "$initial_current_url",
          "$current_domain",
          "$host",
          "$screen_name",
        ],
        before_send(event) {
          if (!event) return event;
          event.properties = {};
          return event;
        },
        disable_session_recording: true,
        disable_surveys: true,
        person_profiles: "never",
        persistence: "memory",
      });
    })
    .catch((error: unknown) => {
      console.error("Unable to initialize product analytics.", error);
    });
}

export function captureProductEvent(
  event:
    | "queue_joined"
    | "queue_called"
    | "queue_started"
    | "queue_completed"
    | "queue_skipped"
    | "queue_cancelled"
    | "service_selected"
    | "notification_opened",
): void {
  if (posthogReady) {
    void posthogReady.then(() => posthog?.capture(event));
  }
}

export function captureApiFailure(status: number, path: string): void {
  if (sentryReady) {
    void sentryReady.then(() =>
      sentry?.captureException(new Error("QueueLess API request failed"), {
        tags: {
          api_status: String(status),
          api_path: path.split("?")[0].replace(uuidPathSegment, ":id"),
        },
      }),
    );
  }
}

export function captureWebSocketFailure(): void {
  if (sentryReady) {
    void sentryReady.then(() =>
      sentry?.captureMessage("QueueLess WebSocket connection failed", {
        level: "warning",
      }),
    );
  }
}
