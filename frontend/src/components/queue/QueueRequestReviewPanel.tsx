import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ErrorState } from "../common/ErrorState";
import { LoadingState } from "../common/LoadingState";
import {
  approveQueueRequest,
  getQueueRequestsForReview,
  rejectQueueRequest,
  type QueueOption,
} from "../../services/queueRequests";
import { useAuthStore } from "../../store/authStore";

export function QueueRequestReviewPanel({
  queues,
}: {
  queues: QueueOption[];
}) {
  const token = useAuthStore((state) => state.token)!;
  const client = useQueryClient();
  const [assignedQueues, setAssignedQueues] = useState<Record<string, string>>({});
  const requests = useQuery({
    queryKey: ["queue-requests", "review"],
    queryFn: () => getQueueRequestsForReview(token, "pending"),
    refetchInterval: 5_000,
  });
  const reviewed = useQuery({
    queryKey: ["queue-requests", "reviewed"],
    queryFn: () => getQueueRequestsForReview(token, "reviewed", 1, 6),
    refetchInterval: 10_000,
  });
  const approve = useMutation({
    mutationFn: ({ requestId, queueId }: { requestId: string; queueId: string }) =>
      approveQueueRequest(requestId, queueId, token),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["queue-requests", "review"] });
      void client.invalidateQueries({ queryKey: ["queue-requests", "reviewed"] });
    },
  });
  const reject = useMutation({
    mutationFn: (requestId: string) => rejectQueueRequest(requestId, token),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["queue-requests", "review"] });
      void client.invalidateQueries({ queryKey: ["queue-requests", "reviewed"] });
    },
  });

  return (
    <section className="mt-8 rounded-2xl border border-ink/10 bg-white p-5 sm:p-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-black">Customer requests</h2>
          <p className="mt-1 text-sm text-ink/60">
            Assign each request to an open queue and approve it to issue a ticket.
          </p>
        </div>
        <span className="rounded-full bg-amber-100 px-3 py-1 text-sm font-bold text-amber-900">
          {requests.data?.pending_total ?? requests.data?.total ?? 0} pending
        </span>
      </div>

      {requests.isLoading && <LoadingState label="Loading customer requests..." />}
      {requests.isError && (
        <div className="mt-4">
          <ErrorState
            message="Unable to load customer requests."
            onRetry={() => void requests.refetch()}
          />
        </div>
      )}
      {requests.data?.items.length === 0 && (
        <p className="mt-5 rounded-xl bg-slate-50 p-4 text-sm text-ink/60">
          No pending requests for review.
        </p>
      )}
      {requests.data && requests.data.items.length > 0 && (
        <div className="mt-5 grid gap-4 lg:grid-cols-2">
          {requests.data.items.map((request) => {
            const availableQueues = queues.filter(
              (queue) =>
                queue.status === "open" &&
                (queue.id === assignedQueues[request.id] ||
                  !assignedQueues[request.id]),
            );
            const selectedQueue = assignedQueues[request.id] ?? "";
            return (
              <article
                className="rounded-xl border border-ink/10 p-4"
                key={request.id}
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <p className="font-bold">{request.customer.full_name}</p>
                    <p className="text-xs text-ink/60">{request.customer.email}</p>
                  </div>
                  <span className="rounded-full bg-amber-50 px-2.5 py-1 text-xs font-bold capitalize text-amber-900">
                    {request.status}
                  </span>
                </div>
                <p className="mt-3 whitespace-pre-wrap text-sm">{request.request_text}</p>
                <p className="mt-2 text-xs text-ink/60">
                  Requested at {request.branch_name} ·{" "}
                  {new Date(request.created_at).toLocaleString()}
                </p>
                {availableQueues.length === 0 ? (
                  <p className="mt-4 text-sm text-amber-800">
                    There are no open queues for this branch.
                  </p>
                ) : (
                  <label className="mt-4 grid gap-1 text-sm font-semibold">
                    Assign to queue
                    <select
                      className="rounded-lg border border-ink/15 p-2"
                      value={selectedQueue}
                      onChange={(event) =>
                        setAssignedQueues((current) => ({
                          ...current,
                          [request.id]: event.target.value,
                        }))
                      }
                    >
                      <option value="">Select an open queue</option>
                      {availableQueues.map((queue) => (
                        <option key={queue.id} value={queue.id}>
                          {queue.name}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
                <div className="mt-4 flex flex-wrap gap-2">
                  <button
                    className="rounded-full bg-ink px-4 py-2 text-sm font-bold text-white disabled:cursor-not-allowed disabled:opacity-50"
                    disabled={
                      !selectedQueue ||
                      approve.isPending ||
                      reject.isPending
                    }
                    onClick={() =>
                      approve.mutate({
                        requestId: request.id,
                        queueId: selectedQueue,
                      })
                    }
                  >
                    {approve.isPending ? "Approving..." : "Approve and issue ticket"}
                  </button>
                  <button
                    className="rounded-full border border-ink/20 px-4 py-2 text-sm font-bold disabled:opacity-50"
                    disabled={approve.isPending || reject.isPending}
                    onClick={() => reject.mutate(request.id)}
                  >
                    {reject.isPending ? "Declining..." : "Decline"}
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      )}
      {reviewed.data?.items.length ? (
        <div className="mt-6">
          <h3 className="font-black">Recently reviewed</h3>
          <div className="mt-3 grid gap-3 lg:grid-cols-2">
            {reviewed.data.items.map((request) => (
              <article
                className="rounded-xl border border-ink/10 bg-slate-50 p-4"
                key={request.id}
              >
                <div className="flex items-start justify-between gap-3">
                  <p className="font-bold">{request.customer.full_name}</p>
                  <span
                    className={`rounded-full px-3 py-1 text-xs font-bold capitalize ${
                      request.status === "approved"
                        ? "bg-emerald-100 text-emerald-900"
                        : "bg-red-100 text-red-900"
                    }`}
                  >
                    {request.status}
                  </span>
                </div>
                <p className="mt-2 line-clamp-2 text-sm">{request.request_text}</p>
                {request.status === "approved" && request.assigned_queue_name && (
                  <p className="mt-2 text-sm font-semibold">
                    Ticket issued in {request.assigned_queue_name}
                    {request.queue_prefix && request.queue_number
                      ? ` · ${request.queue_prefix}${request.queue_number}`
                      : ""}
                  </p>
                )}
                {request.status === "rejected" && request.review_note && (
                  <p className="mt-2 text-sm text-red-800">{request.review_note}</p>
                )}
              </article>
            ))}
          </div>
        </div>
      ) : null}
      {(approve.isError || reject.isError) && (
        <p className="mt-4 text-sm text-red-700" role="alert">
          This request could not be updated. Refresh the list and try again.
        </p>
      )}
    </section>
  );
}
