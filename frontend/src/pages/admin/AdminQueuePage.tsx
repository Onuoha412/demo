import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ErrorState } from "../../components/common/ErrorState";
import { LoadingState } from "../../components/common/LoadingState";
import { PageContainer } from "../../components/common/PageContainer";
import { QRCodeDisplay } from "../../components/common/QRCodeDisplay";
import { useQueueWebSocket } from "../../hooks/useQueueWebSocket";
import { getAdminQueueAudit, verifyAdminQueueEntry } from "../../services/admin";
import { useAuthStore } from "../../store/authStore";
import { formatQueueNumber } from "../../utils/queueNumber";
import { serviceJoinUrl } from "../../utils/queueUrls";

export function AdminQueuePage() {
  const { queueId = "" } = useParams();
  const token = useAuthStore((state) => state.token)!;
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const query = useQuery({
    queryKey: ["admin-queue", queueId, page],
    queryFn: () => getAdminQueueAudit(queueId, token, page),
    enabled: Boolean(queueId),
    refetchInterval: 30_000,
  });
  const verify = useMutation({
    mutationFn: (entryId: string) => verifyAdminQueueEntry(entryId, token),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["admin-queue", queueId] }),
  });
  const connection = useQueueWebSocket(queueId, token);

  if (query.isLoading) return <LoadingState label="Loading queue requests..." />;
  if (query.isError || !query.data) {
    return (
      <ErrorState
        message="Unable to load queue requests."
        onRetry={() => void query.refetch()}
      />
    );
  }

  const queue = query.data;
  const totalPages = Math.max(1, Math.ceil(queue.total_entries / queue.page_size));
  const joinUrl = serviceJoinUrl(queue.service_id, queue.branch_id);

  return (
    <PageContainer className="py-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <Link className="text-sm font-semibold text-emerald-800" to="/admin/queues">
            Back to queues
          </Link>
          <h1 className="mt-2 text-4xl font-black">{queue.name}</h1>
          <p className="mt-2 text-sm text-ink/60">
            {queue.service_name} · Queue status: <span className="capitalize">{queue.status}</span>
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-ink/60">
            Live updates: {connection.status}
          </span>
          <Link
            className="rounded-full border border-ink/15 px-4 py-2 text-sm font-bold"
            to={`/display/${queue.id}`}
            target="_blank"
            rel="noreferrer"
          >
            Open public display
          </Link>
        </div>
      </div>

      <section className="mt-8 overflow-x-auto rounded-2xl bg-white">
        <div className="flex flex-wrap items-center justify-between gap-3 p-5">
          <div>
            <h2 className="text-xl font-black">Customer queue requests</h2>
            <p className="mt-1 text-sm text-ink/60">
              Verify a customer by matching their ticket number and account details. Queue actions remain with assigned staff.
            </p>
          </div>
          <p className="text-sm font-semibold">{queue.total_entries} total requests</p>
        </div>
        <table className="w-full text-left text-sm">
          <thead className="bg-ink/5">
            <tr>
              <th className="p-4">Ticket</th>
              <th className="p-4">Customer</th>
              <th className="p-4">Request</th>
              <th className="p-4">Joined</th>
              <th className="p-4">Status</th>
              <th className="p-4">Verification</th>
              <th className="p-4">Wait</th>
              <th className="p-4">Action</th>
            </tr>
          </thead>
          <tbody>
            {queue.entries.map((entry) => (
              <tr className="border-t" key={entry.id}>
                <td className="p-4 font-bold">
                  {formatQueueNumber(queue.prefix, entry.queue_number)}
                </td>
                <td className="p-4">
                  <div className="font-semibold">{entry.customer.full_name}</div>
                  <div className="text-ink/60">{entry.customer.email}</div>
                </td>
                <td className="max-w-xs whitespace-pre-wrap p-4">
                  {entry.request_note || "No details provided"}
                </td>
                <td className="p-4">{new Date(entry.joined_at).toLocaleString()}</td>
                <td className="p-4 capitalize">{entry.status}</td>
                <td className="p-4">
                  {entry.verified_at ? (
                    <span title={new Date(entry.verified_at).toLocaleString()}>
                      Verified
                    </span>
                  ) : (
                    "Needs verification"
                  )}
                </td>
                <td className="p-4">{entry.estimated_wait_minutes} min</td>
                <td className="p-4">
                  {!entry.verified_at && ["waiting", "called", "serving"].includes(entry.status) && (
                    <button
                      className="rounded-full bg-ink px-4 py-2 text-xs font-bold text-white disabled:opacity-50"
                      disabled={verify.isPending}
                      onClick={() => verify.mutate(entry.id)}
                    >
                      {verify.isPending ? "Verifying..." : "Verify"}
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {queue.entries.length === 0 && (
              <tr>
                <td className="p-5 text-center text-ink/60" colSpan={8}>
                  No customer requests yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
        <div className="flex items-center justify-between gap-3 p-5">
          <button
            className="rounded-full border px-4 py-2 text-sm font-bold disabled:opacity-50"
            disabled={page <= 1}
            onClick={() => setPage((current) => current - 1)}
          >
            Newer requests
          </button>
          <span className="text-sm">Page {page} of {totalPages}</span>
          <button
            className="rounded-full border px-4 py-2 text-sm font-bold disabled:opacity-50"
            disabled={page >= totalPages}
            onClick={() => setPage((current) => current + 1)}
          >
            Older requests
          </button>
        </div>
        {verify.isError && (
          <p className="px-5 pb-5 text-sm text-red-700" role="alert">
            Unable to verify this request. Refresh the page and try again.
          </p>
        )}
      </section>

      <section className="mt-8 max-w-xl">
        <QRCodeDisplay serviceName={`${queue.service_name} — scan to join`} url={joinUrl} />
      </section>
    </PageContainer>
  );
}
