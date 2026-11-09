import { beforeEach, describe, expect, it, vi } from "vitest";

describe("bearer session store", () => {
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
    expect(localStorage.getItem("queueless.remembered")).toBeNull();
    expect(localStorage.getItem("queueless.token")).toBeNull();
    expect(localStorage.getItem("queueless.user")).toBeNull();
    useAuthStore.getState().logout();
    expect(useAuthStore.getState().token).toBeNull();
    expect(sessionStorage.getItem("queueless.session")).toBeNull();
    expect(useAuthStore.getState().ready).toBe(true);
  });

  it("restores a remembered session across browser visits", async () => {
    localStorage.setItem("queueless.remembered", "remembered-session-token");

    const { useAuthStore } = await import("../store/authStore");

    expect(useAuthStore.getState().token).toBe("remembered-session-token");
    useAuthStore.getState().setAuth(
      {
        id: "u2",
        full_name: "Remembered Customer",
        email: "remembered@example.com",
        role: "customer",
        organization_id: null,
        created_at: new Date().toISOString(),
      },
      "remembered-session-token",
      true,
    );
    expect(localStorage.getItem("queueless.remembered")).toBe("remembered-session-token");
    expect(sessionStorage.getItem("queueless.session")).toBeNull();
  });
});
