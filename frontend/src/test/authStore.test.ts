import { beforeEach, describe, expect, it, vi } from "vitest";

describe("tab-scoped bearer session store", () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    vi.resetModules();
  });

  it("clears legacy local credentials without trusting local storage", async () => {
    localStorage.setItem("queueless.token", "stale-token");
    localStorage.setItem("queueless.user", "{invalid json");

    const { useAuthStore } = await import("../store/authStore");

    expect(useAuthStore.getState().token).toBeNull();
    expect(useAuthStore.getState().user).toBeNull();
    expect(useAuthStore.getState().ready).toBe(false);
    expect(localStorage.getItem("queueless.token")).toBeNull();
    expect(localStorage.getItem("queueless.user")).toBeNull();
  });

  it("stores the opaque session token only for the current tab", async () => {
    localStorage.setItem("queueless.token", "stale-token");
    localStorage.setItem("queueless.user", JSON.stringify({ role: "admin" }));

    const { useAuthStore } = await import("../store/authStore");
    const user = {
      id: "u1",
      full_name: "Customer",
      email: "customer@example.com",
      role: "customer" as const,
      organization_id: null,
      created_at: new Date().toISOString(),
    };
    useAuthStore.getState().setAuth(user, "opaque-session-token");
    expect(useAuthStore.getState().user).toEqual(user);
    expect(useAuthStore.getState().token).toBe("opaque-session-token");
    expect(sessionStorage.getItem("queueless.session")).toBe("opaque-session-token");
    expect(localStorage.getItem("queueless.token")).toBeNull();
    expect(localStorage.getItem("queueless.user")).toBeNull();
    useAuthStore.getState().logout();
    expect(useAuthStore.getState().token).toBeNull();
    expect(sessionStorage.getItem("queueless.session")).toBeNull();
    expect(useAuthStore.getState().ready).toBe(true);
  });
});
