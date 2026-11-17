import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { AdminResourcePage } from "../pages/admin/AdminResourcePage";
import { useAuthStore } from "../store/authStore";

const existingUser = {
  id: "user-1",
  full_name: "Existing Admin",
  email: "existing@example.test",
  role: "admin",
  organization_id: null,
  branch_id: null,
  is_active: true,
  approval_pending: false,
  auth_provider: "local",
  last_login_at: null,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

it("filters users and lets an administrator create another administrator", async () => {
  useAuthStore.setState({
    token: "admin-token",
    user: {
      id: "owner-1",
      full_name: "Platform Owner",
      email: "owner@example.test",
      role: "admin",
      organization_id: null,
      created_at: new Date().toISOString(),
    },
    ready: true,
  });
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(
    async (input, init) => {
      const url = new URL(String(input), window.location.origin);
      if (url.pathname.endsWith("/api/v1/admin/users") && init?.method === "POST") {
        return Response.json({
          ...existingUser,
          id: "new-admin",
          full_name: "New Administrator",
          email: "new-admin@example.test",
        }, { status: 201 });
      }
      if (url.pathname.endsWith("/api/v1/admin/users")) {
        return Response.json({
          items: [existingUser],
          total: 1,
          page: 1,
          page_size: 20,
        });
      }
      throw new Error(`Unexpected request: ${url}`);
    },
  );
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/admin/users"]}>
        <Routes>
          <Route path="/admin/:resource" element={<AdminResourcePage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );

  expect(await screen.findByText(/existing@example\.test/)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Search"), {
    target: { value: "new-admin@example.test" },
  });
  fireEvent.change(await screen.findByLabelText("Filter by role"), {
    target: { value: "admin" },
  });
  fireEvent.change(await screen.findByLabelText("Filter by account status"), {
    target: { value: "true" },
  });
  fireEvent.change(await screen.findByLabelText("Filter by sign-in method"), {
    target: { value: "local" },
  });

  await waitFor(() => {
    const userSearch = fetchMock.mock.calls
      .map(([input]) => new URL(String(input), window.location.origin))
      .find((url) => url.searchParams.get("auth_provider") === "local");
    expect(userSearch?.searchParams.get("search")).toBe("new-admin@example.test");
    expect(userSearch?.searchParams.get("role")).toBe("admin");
    expect(userSearch?.searchParams.get("active")).toBe("true");
  });

  fireEvent.change(await screen.findByLabelText("full name"), {
    target: { value: "New Administrator" },
  });
  fireEvent.change(screen.getByLabelText("email"), {
    target: { value: "new-admin@example.test" },
  });
  fireEvent.change(screen.getByLabelText("password"), {
    target: { value: "new-admin-password" },
  });
  fireEvent.change(screen.getByLabelText("role"), {
    target: { value: "admin" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Create" }));

  await waitFor(() => {
    const createCall = fetchMock.mock.calls.find(
      ([input, init]) =>
        new URL(String(input), window.location.origin).pathname.endsWith("/api/v1/admin/users") &&
        init?.method === "POST",
    );
    expect(JSON.parse(String(createCall?.[1]?.body))).toMatchObject({
      full_name: "New Administrator",
      email: "new-admin@example.test",
      password: "new-admin-password",
      role: "admin",
    });
  });

});

it("lets an organization administrator approve a pending staff account", async () => {
  const pendingStaff = {
    ...existingUser,
    id: "pending-staff",
    full_name: "New Staff Member",
    email: "pending-staff@example.test",
    role: "staff",
    organization_id: "org-1",
    branch_id: "branch-1",
    is_active: false,
    approval_pending: true,
    organization_approved: true,
  };
  useAuthStore.setState({
    token: "admin-token",
    user: {
      id: "org-admin",
      full_name: "Organization Admin",
      email: "admin@example.test",
      role: "admin",
      organization_id: "org-1",
      created_at: new Date().toISOString(),
    },
    ready: true,
  });
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(
    async (input, init) => {
      const url = new URL(String(input), window.location.origin);
      if (url.pathname.endsWith("/api/v1/admin/users/pending-staff/approve")) {
        return Response.json({
          ...pendingStaff,
          is_active: true,
          approval_pending: false,
        });
      }
      if (url.pathname.endsWith("/api/v1/admin/users")) {
        return Response.json({
          items: [pendingStaff],
          total: 1,
          page: 1,
          page_size: 20,
        });
      }
      throw new Error(`Unexpected request: ${url.pathname} ${init?.method ?? "GET"}`);
    },
  );
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/admin/users"]}>
        <Routes>
          <Route path="/admin/:resource" element={<AdminResourcePage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );

  fireEvent.click(await screen.findByRole("button", { name: "Approve account" }));

  await waitFor(() => {
    expect(
      fetchMock.mock.calls.some(
        ([input, init]) =>
          new URL(String(input), window.location.origin).pathname.endsWith(
            "/api/v1/admin/users/pending-staff/approve",
          ) && init?.method === "POST",
      ),
    ).toBe(true);
  });
});
