import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { useLocation } from "react-router-dom";

import { ApiError } from "../../services/api";
import { submitFeedback, type FeedbackCategory } from "../../services/feedback";
import { useAuthStore } from "../../store/authStore";

const categories: { value: FeedbackCategory; label: string }[] = [
  { value: "general", label: "General feedback" },
  { value: "bug", label: "Bug or technical problem" },
  { value: "feature_request", label: "Feature request" },
  { value: "ui_accessibility", label: "Interface or accessibility issue" },
  { value: "queue_accuracy", label: "Queue position or wait estimate" },
  { value: "performance_connection", label: "Performance or connection" },
  { value: "security_privacy", label: "Security or privacy concern" },
  { value: "account_login", label: "Account or login problem" },
  { value: "staff_service", label: "Staff service experience" },
  { value: "organization_setup_migration", label: "Organization setup or migration" },
  { value: "notification", label: "Notification problem" },
  { value: "other", label: "Other" },
];

function currentPageIdentifier(pathname: string): string {
  return pathname
    .split("/")
    .map((segment) =>
      /^[0-9a-f]{8}-[0-9a-f-]{27,}$/i.test(segment) ? ":id" : segment,
    )
    .join("/")
    .slice(0, 160);
}

function newIdempotencyKey(): string {
  return globalThis.crypto?.randomUUID?.() ??
    `${Date.now()}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`;
}

export function FeedbackEntryPoint() {
  const location = useLocation();
  const user = useAuthStore((state) => state.user);
  const [open, setOpen] = useState(false);
  const [category, setCategory] = useState<FeedbackCategory>("general");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [suggestion, setSuggestion] = useState("");
  const [rating, setRating] = useState("");
  const [anonymous, setAnonymous] = useState(false);
  const [shareQueueContext, setShareQueueContext] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [reportId, setReportId] = useState("");
  const submissionKey = useRef<string | null>(null);
  const titleId = useId();

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !busy) setOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [busy, open]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    submissionKey.current ??= newIdempotencyKey();
    try {
      const report = await submitFeedback({
        category,
        title: title.trim(),
        description: description.trim(),
        improvement_suggestion: suggestion.trim() || undefined,
        rating: rating ? Number(rating) : undefined,
        is_anonymous: anonymous,
        page_identifier: currentPageIdentifier(location.pathname),
        app_version: "0.1.0",
        queue_context_entry_id:
          user && !anonymous && shareQueueContext
            ? location.pathname.match(/^\/queue\/([0-9a-f-]{36})$/i)?.[1]
            : undefined,
        idempotency_key: submissionKey.current,
      });
      submissionKey.current = null;
      setReportId(report.id);
    } catch (submitError) {
      setError(
        submitError instanceof ApiError
          ? submitError.message
          : "Feedback could not be submitted. Please try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={() => {
          setOpen(true);
          setError("");
          setReportId("");
          submissionKey.current = null;
        }}
        className="fixed bottom-4 right-4 z-40 rounded-full bg-emerald-800 px-5 py-3 text-sm font-bold text-white shadow-lg transition hover:bg-emerald-950 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-800"
        aria-haspopup="dialog"
      >
        Feedback
      </button>
      {open && (
        <div
          className="fixed inset-0 z-50 flex items-end justify-center bg-ink/50 p-0 sm:items-center sm:p-4"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget && !busy) setOpen(false);
          }}
        >
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            className="max-h-[92vh] w-full overflow-y-auto rounded-t-3xl bg-white p-6 shadow-2xl sm:max-w-xl sm:rounded-3xl sm:p-8"
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 id={titleId} className="text-2xl font-black">Share feedback</h2>
                <p className="mt-1 text-sm text-ink/65">
                  Your report goes to the team responsible for reviewing QueueLess feedback.
                </p>
              </div>
              <button
                type="button"
                className="rounded-full p-2 text-ink/70 hover:bg-ink/5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-800"
                aria-label="Close feedback form"
                disabled={busy}
                onClick={() => setOpen(false)}
              >
                <span aria-hidden="true">Close</span>
              </button>
            </div>
            {reportId ? (
              <div className="mt-6 rounded-2xl border border-emerald-800/20 bg-emerald-50 p-5" role="status">
                <h3 className="font-bold text-emerald-950">Feedback received</h3>
                <p className="mt-2 text-sm text-emerald-950">
                  Your reference is <code className="break-all font-bold">{reportId}</code>.
                  {user && !anonymous
                    ? " You can review its status in your Feedback history."
                    : " This report was sent anonymously, so we cannot reply to you about it."}
                </p>
                <button
                  type="button"
                  className="mt-4 rounded-full bg-ink px-4 py-2 text-sm font-bold text-white"
                  onClick={() => setOpen(false)}
                >
                  Done
                </button>
              </div>
            ) : (
              <form className="mt-6 space-y-4" onSubmit={(event) => void submit(event)}>
                <label className="block text-sm font-semibold" htmlFor="feedback-category">
                  Category
                  <select
                    id="feedback-category"
                    value={category}
                    onChange={(event) => {
                      submissionKey.current = null;
                      setCategory(event.target.value as FeedbackCategory);
                    }}
                    className="mt-1 block w-full rounded-xl border border-ink/20 bg-white px-3 py-2.5"
                  >
                    {categories.map((item) => (
                      <option key={item.value} value={item.value}>{item.label}</option>
                    ))}
                  </select>
                </label>
                {category === "security_privacy" && (
                  <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-950" role="note">
                    Security and privacy reports are restricted to Super Admin reviewers.
                    Do not include passwords, tokens, or other secrets.
                  </p>
                )}
                <label className="block text-sm font-semibold" htmlFor="feedback-title">
                  Short title
                  <input
                    id="feedback-title"
                    required
                    minLength={3}
                    maxLength={160}
                    value={title}
                    onChange={(event) => {
                      submissionKey.current = null;
                      setTitle(event.target.value);
                    }}
                    className="mt-1 block w-full rounded-xl border border-ink/20 px-3 py-2.5"
                  />
                </label>
                <label className="block text-sm font-semibold" htmlFor="feedback-description">
                  What happened?
                  <textarea
                    id="feedback-description"
                    required
                    minLength={10}
                    maxLength={5000}
                    rows={4}
                    value={description}
                    onChange={(event) => {
                      submissionKey.current = null;
                      setDescription(event.target.value);
                    }}
                    className="mt-1 block w-full rounded-xl border border-ink/20 px-3 py-2.5"
                    aria-describedby="feedback-privacy"
                  />
                </label>
                <p id="feedback-privacy" className="text-xs text-ink/60">
                  We attach only the page type and app version. Do not include passwords,
                  payment details, or private queue information.
                </p>
                {["feature_request", "general", "other"].includes(category) && (
                  <label className="block text-sm font-semibold" htmlFor="feedback-suggestion">
                    Suggested improvement <span className="font-normal text-ink/60">(optional)</span>
                    <textarea
                      id="feedback-suggestion"
                      maxLength={3000}
                      rows={2}
                      value={suggestion}
                      onChange={(event) => {
                        submissionKey.current = null;
                        setSuggestion(event.target.value);
                      }}
                      className="mt-1 block w-full rounded-xl border border-ink/20 px-3 py-2.5"
                    />
                  </label>
                )}
                {["general", "queue_accuracy", "staff_service"].includes(category) && (
                  <label className="block text-sm font-semibold" htmlFor="feedback-rating">
                    Rate your experience <span className="font-normal text-ink/60">(optional)</span>
                    <select
                      id="feedback-rating"
                      value={rating}
                      onChange={(event) => {
                        submissionKey.current = null;
                        setRating(event.target.value);
                      }}
                      className="mt-1 block w-full rounded-xl border border-ink/20 bg-white px-3 py-2.5"
                    >
                      <option value="">Skip rating</option>
                      <option value="1">1 — Very poor</option>
                      <option value="2">2 — Poor</option>
                      <option value="3">3 — Okay</option>
                      <option value="4">4 — Good</option>
                      <option value="5">5 — Excellent</option>
                    </select>
                  </label>
                )}
                {user && (
                  <label className="flex items-start gap-3 text-sm">
                    <input
                      type="checkbox"
                      checked={anonymous}
                      onChange={(event) => {
                        submissionKey.current = null;
                        setAnonymous(event.target.checked);
                      }}
                      className="mt-1"
                    />
                    <span>
                      Submit anonymously
                      <span className="mt-0.5 block text-xs text-ink/60">
                        We will not link this report to your account. Anonymous reports may
                        limit our ability to investigate or reply to an individual case.
                      </span>
                    </span>
                  </label>
                )}
                {user?.role === "customer" &&
                  location.pathname.match(/^\/queue\/([0-9a-f-]{36})$/i) &&
                  !anonymous && (
                    <label className="flex items-start gap-3 text-sm">
                      <input
                        type="checkbox"
                        checked={shareQueueContext}
                        onChange={(event) => {
                          submissionKey.current = null;
                          setShareQueueContext(event.target.checked);
                        }}
                        className="mt-1"
                      />
                      <span>
                        Share this queue's organization context with reviewers
                        <span className="mt-0.5 block text-xs text-ink/60">
                          We use the queue entry to verify the organization and branch, then
                          discard the entry identifier. Your position and ticket details are
                          not stored with this feedback.
                        </span>
                      </span>
                    </label>
                  )}
                {error && <p className="text-sm text-red-800" role="alert">{error}</p>}
                <div className="flex flex-wrap justify-end gap-2 pt-2">
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => setOpen(false)}
                    className="rounded-full border border-ink/20 px-5 py-2.5 text-sm font-bold"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={busy}
                    className="rounded-full bg-ink px-5 py-2.5 text-sm font-bold text-white disabled:opacity-60"
                  >
                    {busy ? "Sending..." : "Send feedback"}
                  </button>
                </div>
              </form>
            )}
          </section>
        </div>
      )}
    </>
  );
}
