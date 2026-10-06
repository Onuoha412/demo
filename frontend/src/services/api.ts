const API_BASE = import.meta.env.VITE_API_URL || "";

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

const getHeaders = (token?: string) => ({
  "Content-Type": "application/json",
  ...(token ? { Authorization: `Bearer ${token}` } : {}),
});

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
  token?: string,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: { ...getHeaders(token), ...(options.headers || {}) },
    });
  } catch {
    throw new ApiError(0, "Network error. Please check your connection.");
  }
  if (!response.ok) {
    const maybeJson = await response
      .json()
      .catch(() => ({ detail: "Unexpected API error" }));
    throw new ApiError(response.status, maybeJson.detail || "Unexpected API error");
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
