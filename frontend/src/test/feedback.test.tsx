import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { FeedbackEntryPoint } from "../components/common/FeedbackEntryPoint";
import { useAuthStore } from "../store/authStore";

const entryId = "123e4567-e89b-12d3-a456-426614174000";

beforeEach(() => {
  useAuthStore.setState({
    token: "feedback-session",
    user: {
      id: "customer-1",
      full_name: "Feedback Customer",
      email: "customer@example.test",
      role: "customer",
      organization_id: null,
      created_at: new Date().toISOString(),
    },
    ready: true,
  });
  vi.restoreAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

it("submits minimal page context, retries idempotently, and confirms the stored reference", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch");
  fetchMock
    .mockResolvedValueOnce(
      Response.json({ detail: "Temporary failure" }, { status: 503 }),
    )
    .mockResolvedValueOnce(
      Response.json({
        id: "report-1",
        category: "queue_accuracy",
        title: "Wait estimate is misleading",
      }),
    );

  render(
    <MemoryRouter initialEntries={[`/queue/${entryId}`]}>
      <FeedbackEntryPoint />
    </MemoryRouter>,
  );

  fireEvent.click(screen.getByRole("button", { name: "Feedback" }));
  fireEvent.change(screen.getByLabelText("Category"), {
    target: { value: "queue_accuracy" },
  });
  fireEvent.change(screen.getByLabelText("Short title"), {
    target: { value: "Wait estimate is misleading" },
  });
  fireEvent.change(screen.getByLabelText("What happened?"), {
    target: { value: "The estimate was much shorter than the actual wait." },
  });
  fireEvent.click(
    screen.getByLabelText(/share this queue's organization context/i),
  );
  fireEvent.click(screen.getByRole("button", { name: "Send feedback" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("Temporary failure");
  fireEvent.click(screen.getByRole("button", { name: "Send feedback" }));
  expect(await screen.findByText("Feedback received")).toBeInTheDocument();
  expect(screen.getByText("report-1")).toBeInTheDocument();

  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  const requestBodies = fetchMock.mock.calls.map(([, options]) =>
    JSON.parse(String(options?.body)),
  );
  expect(requestBodies[0].page_identifier).toBe("/queue/:id");
  expect(requestBodies[0].queue_context_entry_id).toBe(entryId);
  expect(requestBodies[0].idempotency_key).toBe(requestBodies[1].idempotency_key);
});
