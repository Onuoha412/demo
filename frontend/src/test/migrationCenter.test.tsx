import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { MigrationCenterPage } from "../pages/admin/MigrationCenterPage";
import { useAuthStore } from "../store/authStore";

const previewJob = {
  id: "job-1",
  organization_id: "org-1",
  source_system: "legacy-system",
  file_sha256: "a".repeat(64),
  status: "preview",
  total_rows: 1,
  valid_rows: 1,
  invalid_rows: 0,
  created_rows: 0,
  skipped_rows: 0,
  rejected_rows: 0,
  preview_rows: [
    { row_number: 2, external_id: "customer-1", status: "valid", errors: [] },
  ],
  result_rows: [],
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

beforeEach(() => {
  useAuthStore.setState({
    token: "admin-session",
    user: {
      id: "admin-1",
      full_name: "Organization Admin",
      email: "admin@example.test",
      role: "admin",
      organization_id: "org-1",
      created_at: new Date().toISOString(),
    },
    ready: true,
  });

  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = new URL(String(input), window.location.origin);
    if (url.pathname.endsWith("/api/v1/admin/migrations") && init?.method !== "POST") {
      return Response.json({ items: [], total: 0, page: 1, page_size: 50 });
    }
    if (url.pathname.endsWith("/api/v1/admin/migrations/preview")) {
      return Response.json(previewJob);
    }
    if (url.pathname.endsWith("/api/v1/admin/migrations/job-1/import")) {
      return Response.json({
        ...previewJob,
        status: "completed",
        created_rows: 1,
        preview_rows: [],
        result_rows: [
          { row_number: 2, external_id: "customer-1", status: "created", errors: [] },
        ],
      });
    }
    throw new Error(`Unexpected request: ${url.pathname}`);
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

it("uploads a file as multipart data and requires explicit import confirmation", async () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <MigrationCenterPage />
    </QueryClientProvider>,
  );
  expect(
    await screen.findByRole("heading", { name: "Migration Center" }),
  ).toBeInTheDocument();
  const user = userEvent.setup();
  expect(screen.getByLabelText("Source system")).toHaveProperty(
    "validity.valid",
    true,
  );

  const file = new File(
    ["external_id,full_name,email,role,branch_id\ncustomer-1,Test Customer,test@example.test,customer,\n"],
    "customers.csv",
    { type: "text/csv" },
  );
  await user.upload(screen.getByLabelText(/CSV file/), file);
  const fileInput = screen.getByLabelText(/CSV file/);
  expect(fileInput).toHaveProperty("files.0", file);
  expect((fileInput as HTMLInputElement).checkValidity()).toBe(true);
  await user.click(screen.getByRole("button", { name: "Upload and preview" }));

  expect(await screen.findByRole("heading", { name: "Import preview" })).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "Confirm and import" }),
  ).toBeDisabled();
  await user.click(
    screen.getByRole("checkbox", {
      name: /I reviewed this preview and authorize importing/,
    }),
  );
  await user.click(screen.getByRole("button", { name: "Confirm and import" }));

  expect(
    await screen.findByText("Import completed and recorded in migration history."),
  ).toBeInTheDocument();
  const requests = vi.mocked(globalThis.fetch).mock.calls;
  const previewRequest = requests.find(([url]) =>
    String(url).endsWith("/api/v1/admin/migrations/preview"),
  );
  expect(previewRequest?.[1]?.body).toBeInstanceOf(FormData);
  expect(new Headers(previewRequest?.[1]?.headers).has("Content-Type")).toBe(false);
  await waitFor(() => {
    expect(requests.some(([url]) =>
      String(url).endsWith("/api/v1/admin/migrations/job-1/import"),
    )).toBe(true);
  });
});
