import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { ErrorState } from "../common/ErrorState";
import { LoadingState } from "../common/LoadingState";
import { getBranches } from "../../services/queue";
import {
  createQueueRequest,
  getMyQueueRequests,
  type QueueRequest,
} from "../../services/queueRequests";
import { useAuthStore } from "../../store/authStore";
import { formatQueueNumber } from "../../utils/queueNumber";

function RequestStatusCard({ request }: { request: QueueRequest }) {
  const statusStyle =
    request.status === "approved"
      ? "bg-emerald-100 text-emerald-900"
      : request.status === "rejected"
        ? "bg-red-100 text-red-900"
        : "bg-amber-100 text-amber-900";

  return (
    <article className="rounded-xl border border-ink/10 bg-white p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-bold">{request.branch_name}</p>
        <span className={`rounded-full px-3 py-1 text-xs font-bold capitalize ${statusStyle}`}>
          {request.status}
        </span>
      </div>
      <p className="mt-3 whitespace-pre-wrap text-sm">{request.request_text}</p>
      {request.status === "pending" && (
        <p className="mt-3 text-sm text-ink/60">
          The service team will assign your request to an open queue.
        </p>
      )}
      {request.status === "rejected" && request.review_note && (
        <p className="mt-3 text-sm text-red-800">
          Team response: {request.review_note}
        </p>
      )}
      {request.status === "approved" && request.queue_entry_id && (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm font-semibold">
            {request.assigned_queue_name} · Ticket{" "}
            {formatQueueNumber(request.queue_prefix ?? "", request.queue_number ?? 0)}
          </p>
          <Link
            className="rounded-full bg-ink px-4 py-2 text-sm font-bold text-white"
            to={`/queue/${request.queue_entry_id}`}
          >
            View queue ticket
          </Link>
        </div>
      )}
    </article>
  );
}

export function MyQueueRequestsPanel() {
  const token = useAuthStore((state) => state.token);
  const client = useQueryClient();
  const [branchId, setBranchId] = useState("");
  const [requestText, setRequestText] = useState("");
  const branches = useQuery({
    queryKey: ["queue-request-branches"],
    queryFn: () => getBranches(),
    enabled: Boolean(token),
  });
  const requests = useQuery({
    queryKey: ["queue-requests", "mine"],
    queryFn: () => getMyQueueRequests(token!),
    enabled: Boolean(token),
    refetchInterval: 5_000,
  });
  const submit = useMutation({
    mutationFn: () =>
      createQueueRequest(
        { branch_id: branchId, request_text: requestText.trim() },
        token!,
      ),
    onSuccess: () => {
      setRequestText("");
      void client.invalidateQueries({ queryKey: ["queue-requests", "mine"] });
    },
  });

  if (!token) {
    return (
      <section className="mt-8 rounded-2xl border border-ink/10 bg-white p-6">
        <h2 className="text-xl font-black">Need help with something?</h2>
        <p className="mt-2 text-sm text-ink/65">
          Sign in or create an account to send a free-form request to a service team.
        </p>
        <div className="mt-4 flex gap-3">
          <Link className="rounded-full bg-ink px-4 py-2 text-sm font-bold text-white" to="/login">
            Sign in
          </Link>
          <Link className="rounded-full border px-4 py-2 text-sm font-bold" to="/register">
            Register
          </Link>
        </div>
      </section>
    );
  }

  return (
    <section className="mt-8 rounded-2xl border border-ink/10 bg-white p-5 sm:p-6">
      <h2 className="text-2xl font-black">Request a queue spot</h2>
      <p className="mt-1 text-sm text-ink/60">
        Tell us what you need and choose a branch. A staff member or administrator
        will assign an open queue and approve your request before a ticket is issued.
      </p>
      <form
        className="mt-5 grid gap-3 sm:grid-cols-[minmax(0,1fr)_2fr_auto]"
        onSubmit={(event) => {
          event.preventDefault();
          submit.mutate();
        }}
      >
        <label className="grid gap-1 text-sm font-semibold">
          Branch
          <select
            className="min-h-11 rounded-lg border border-ink/15 p-2"
            value={branchId}
            onChange={(event) => setBranchId(event.target.value)}
            required
            disabled={branches.isLoading || !branches.data?.length}
          >
            <option value="">Choose a branch</option>
            {(branches.data ?? []).map((branch) => (
              <option key={branch.id} value={branch.id}>
                {branch.name}
              </option>
            ))}
          </select>
        </label>
        <label className="grid gap-1 text-sm font-semibold">
          What do you need?
          <input
            className="min-h-11 rounded-lg border border-ink/15 p-2 font-normal"
            maxLength={1000}
            minLength={3}
            placeholder="Describe any service or assistance you need."
            value={requestText}
            onChange={(event) => setRequestText(event.target.value)}
            required
          />
        </label>
        <button
          className="self-end rounded-full bg-ink px-5 py-3 text-sm font-bold text-white disabled:opacity-50"
          type="submit"
          disabled={
            submit.isPending ||
            !branchId ||
            requestText.trim().length < 3 ||
            branches.isLoading
          }
        >
          {submit.isPending ? "Sending..." : "Send request"}
        </button>
      </form>
      {branches.isError && (
        <div className="mt-4">
          <ErrorState
            message="Unable to load available branches."
            onRetry={() => void branches.refetch()}
          />
        </div>
      )}
      {branches.data?.length === 0 && (
        <p className="mt-4 text-sm text-amber-800">
          There are no branches accepting requests right now.
        </p>
      )}
      {submit.isError && (
        <p className="mt-3 text-sm text-red-700" role="alert">
          Your request could not be sent. Please try again.
        </p>
      )}

      <div className="mt-8">
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-lg font-black">Your requests</h3>
          {requests.data && (
            <span className="text-sm text-ink/60">{requests.data.length} total</span>
          )}
        </div>
        {requests.isLoading && <LoadingState label="Loading your requests..." />}
        {requests.isError && (
          <div className="mt-3">
            <ErrorState
              message="Unable to load your request cards."
              onRetry={() => void requests.refetch()}
            />
          </div>
        )}
        {requests.data?.length === 0 && (
          <p className="mt-3 rounded-xl bg-slate-50 p-4 text-sm text-ink/60">
            Your submitted requests will appear here.
          </p>
        )}
        {requests.data && requests.data.length > 0 && (
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {requests.data.map((request) => (
              <RequestStatusCard key={request.id} request={request} />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
