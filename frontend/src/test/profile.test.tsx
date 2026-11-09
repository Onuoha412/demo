import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import App from "../App";
import { useAuthStore } from "../store/authStore";

function renderProfile() {
  window.history.pushState({}, "", "/profile");
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.restoreAllMocks();
  sessionStorage.clear();
  useAuthStore.setState({
    token: "profile-session",
    ready: true,
    user: {
      id: "customer-1",
      full_name: "Sample Customer",
      email: "sample@example.test",
      role: "customer",
      organization_id: null,
      created_at: new Date().toISOString(),
    },
  });
});

it("saves a real profile name update and refreshes authenticated user state", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
    Response.json({
      id: "customer-1",
      full_name: "Updated Customer",
      email: "sample@example.test",
      role: "customer",
      organization_id: null,
      created_at: new Date().toISOString(),
    }),
  );
  renderProfile();

  fireEvent.change(await screen.findByLabelText("Full name"), {
    target: { value: "Updated Customer" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Save profile" }));

  expect(await screen.findByRole("status")).toHaveTextContent(
    "Your profile has been updated.",
  );
  expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining("/api/v1/auth/me"),
    expect.objectContaining({
      method: "PATCH",
      body: JSON.stringify({ full_name: "Updated Customer" }),
    }),
  );
  expect(useAuthStore.getState().user?.full_name).toBe("Updated Customer");
});

it("validates password confirmation before submitting and updates via the API", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
    Response.json({
      message: "Password changed. Other active sessions have been signed out.",
    }),
  );
  renderProfile();
  fireEvent.change(await screen.findByLabelText("Current password"), {
    target: { value: "current-password" },
  });
  fireEvent.change(screen.getByLabelText("New password"), {
    target: { value: "new-password-123" },
  });
  fireEvent.change(screen.getByLabelText("Confirm new password"), {
    target: { value: "different-password" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Update password" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "The new passwords do not match.",
  );
  expect(fetchMock).not.toHaveBeenCalled();

  fireEvent.change(screen.getByLabelText("Confirm new password"), {
    target: { value: "new-password-123" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Update password" }));

  expect(await screen.findByRole("status")).toHaveTextContent(
    "Other active sessions have been signed out.",
  );
  expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining("/api/v1/auth/change-password"),
    expect.objectContaining({
      method: "POST",
      body: JSON.stringify({
        current_password: "current-password",
        new_password: "new-password-123",
      }),
    }),
  );
});
