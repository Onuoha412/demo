import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { ErrorState } from "../../components/common/ErrorState";
import { LoadingState } from "../../components/common/LoadingState";
import { PageContainer } from "../../components/common/PageContainer";
import { getSuperAdminAuditLogs } from "../../services/superAdmin";
import { useAuthStore } from "../../store/authStore";

export function SuperAdminAuditPage() {
  const [page, setPage] = useState(1);
  const token = useAuthStore((state) => state.token)!;
  const query = useQuery({
    queryKey: ["super-admin-audit-logs", page],
    queryFn: () => getSuperAdminAuditLogs(token, page),
  });

  if (query.isLoading) return <LoadingState label="Loading security audit log..." />;
  if (!query.data) {
    return (
      <ErrorState
        message="Unable to load the security audit log."
        onRetry={() => void query.refetch()}
      />
    );
  }

  const pageCount = Math.max(1, Math.ceil(query.data.total / query.data.page_size));
  return (
    <PageContainer className="py-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <Link className="text-sm font-bold text-emerald-800 underline" to="/super-admin/dashboard">
            Super Admin dashboard
          </Link>
          <h1 className="mt-2 text-4xl font-black">Security audit log</h1>
        </div>
        <p className="text-sm text-ink/60">{query.data.total} recorded events</p>
      </div>
      {query.isError && (
        <p className="mt-4 rounded-xl bg-amber-50 p-3 text-sm text-amber-900" role="alert">
          The audit log could not refresh. Showing the previously loaded page.{" "}
          <button className="font-bold underline" onClick={() => void query.refetch()}>
            Retry
          </button>
        </p>
      )}
      <div className="mt-6 overflow-x-auto rounded-2xl bg-white">
        <table className="w-full text-left text-sm">
          <thead className="bg-ink/5">
            <tr>
              <th className="p-4">Time</th>
              <th className="p-4">Actor</th>
              <th className="p-4">Action</th>
              <th className="p-4">Target</th>
              <th className="p-4">Details</th>
            </tr>
          </thead>
          <tbody>
            {query.data.items.map((event) => (
              <tr key={event.id} className="border-t align-top">
                <td className="whitespace-nowrap p-4">
                  {new Date(event.created_at).toLocaleString()}
                </td>
                <td className="p-4">{event.actor_email ?? "System"}</td>
                <td className="p-4 font-semibold">{event.action}</td>
                <td className="p-4">
                  {event.target_type}
                  {event.target_id ? ` · ${event.target_id}` : ""}
                </td>
                <td className="max-w-sm break-words p-4 text-ink/70">
                  {Object.entries(event.details)
                    .map(([key, value]) => `${key}: ${String(value)}`)
                    .join(" · ") || "—"}
                </td>
              </tr>
            ))}
            {!query.data.items.length && (
              <tr>
                <td className="p-6 text-center text-ink/60" colSpan={5}>
                  No administrative security events have been recorded yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="mt-4 flex items-center justify-between gap-4">
        <button
          className="rounded-full border px-4 py-2 text-sm font-bold disabled:opacity-50"
          disabled={page <= 1}
          onClick={() => setPage((current) => current - 1)}
        >
          Previous
        </button>
        <span className="text-sm text-ink/60">
          Page {page} of {pageCount}
        </span>
        <button
          className="rounded-full border px-4 py-2 text-sm font-bold disabled:opacity-50"
          disabled={page >= pageCount}
          onClick={() => setPage((current) => current + 1)}
        >
          Next
        </button>
      </div>
    </PageContainer>
  );
}
