import { captureApiFailure } from "../observability";
import { useAuthStore } from "../store/authStore";

const LOCAL_API_ORIGINS = new Set(["localhost", "127.0.0.1", "[::1]"]);

export function resolveApiBaseUrl(
  configuredUrl: string | undefined,
  isDevServer: boolean,
  hostname: string | undefined,
): string {
  const configured = configuredUrl?.trim().replace(/\/+$/, "");
  if (configured) return configured;
  if (!isDevServer && hostname && LOCAL_API_ORIGINS.has(hostname)) {
    return "http://localhost:8000";
  }
  return "";
}

export const API_BASE = resolveApiBaseUrl(
  import.meta.env.VITE_API_URL,
  import.meta.env.DEV,
  typeof window === "undefined" ? undefined : window.location.hostname,
);

export function resolveWebSocketBaseUrl(
  configuredUrl: string | undefined,
  apiBaseUrl: string,
  protocol: string | undefined,
  host: string | undefined,
): string {
  const configured = configuredUrl?.trim().replace(/\/+$/, "");
  if (configured) return configured;
  if (apiBaseUrl) return apiBaseUrl.replace(/^http/, "ws").replace(/\/+$/, "");
  if (protocol && host) {
    return `${protocol === "https:" ? "wss" : "ws"}://${host}`;
  }
  return "";
}

export const WS_BASE = resolveWebSocketBaseUrl(
  import.meta.env.VITE_WS_URL,
  API_BASE,
  typeof window === "undefined" ? undefined : window.location.protocol,
  typeof window === "undefined" ? undefined : window.location.host,
);

function formatApiError(status: number, body: string): string {
  let payload: unknown;
  try {
    payload = JSON.parse(body);
  } catch {
    payload = undefined;
  }

  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = payload.detail;
    if (typeof detail === "string" && detail.trim()) return detail;
    if (Array.isArray(detail)) {
      const messages = detail
        .map((item: unknown) => {
          if (!item || typeof item !== "object") return null;
          const message = "msg" in item && typeof item.msg === "string" ? item.msg : null;
          const location =
            "loc" in item && Array.isArray(item.loc)
            ? item.loc.filter((part: unknown): part is string | number =>
                  typeof part === "string" || typeof part === "number",
                )
              : [];
          return message
            ? `${location.length ? `${location.join(".")}: ` : ""}${message}`
            : null;
        })
        .filter((message): message is string => message !== null);
      if (messages.length) return messages.join(" ");
    }
  }

  if (status === 404) {
    return "API endpoint not found. Check that the frontend is connected to the QueueLess backend.";
  }
  if (status >= 500) {
    return "The QueueLess backend could not complete the request. Check that the database is initialized and the API is healthy.";
  }
  return `The QueueLess API request failed (HTTP ${status}). Please try again.`;
}

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
  sessionToken?: string,
): Promise<T> {
  const token = sessionToken ?? useAuthStore.getState().token;
  let response: Response;
  const headers = new Headers(options.headers);
  if (
    options.body !== undefined &&
    !(options.body instanceof FormData) &&
    !headers.has("Content-Type")
  ) {
    headers.set("Content-Type", "application/json");
  }
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...options,
      credentials: "omit",
      headers,
    });
  } catch {
    captureApiFailure(0, path);
    throw new ApiError(
      0,
      `Cannot reach the QueueLess API${API_BASE ? ` at ${API_BASE}` : ""}. Check that the backend is running and the API URL is configured.`,
    );
  }
  if (!response.ok) {
    captureApiFailure(response.status, path);
    if (
      response.status === 401 &&
      !path.endsWith("/auth/login") &&
      !path.endsWith("/auth/register")
    ) {
      useAuthStore.getState().logout();
    }
    const body = await response.text();
    throw new ApiError(response.status, formatApiError(response.status, body));
  }
  if (response.status === 204) return undefined as T;
  try {
    return (await response.json()) as T;
  } catch {
    captureApiFailure(response.status, path);
    throw new ApiError(
      response.status,
      "The QueueLess backend returned an invalid response. Check that the API URL points to the backend, not the frontend.",
    );
  }
}

export async function apiDownload(
  path: string,
  sessionToken?: string,
): Promise<Blob> {
  const token = sessionToken ?? useAuthStore.getState().token;
  const headers = new Headers();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      credentials: "omit",
      headers,
    });
  } catch {
    captureApiFailure(0, path);
    throw new ApiError(
      0,
      `Cannot reach the QueueLess API${API_BASE ? ` at ${API_BASE}` : ""}. Check that the backend is running and the API URL is configured.`,
    );
  }

  if (!response.ok) {
    captureApiFailure(response.status, path);
    if (response.status === 401) useAuthStore.getState().logout();
    throw new ApiError(
      response.status,
      formatApiError(response.status, await response.text()),
    );
  }

  return response.blob();
}
