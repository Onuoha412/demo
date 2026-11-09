import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Bell, MapPin, TicketCheck } from "lucide-react";
import { Link } from "react-router-dom";

import { EmptyState } from "../common/EmptyState";
import { ErrorState } from "../common/ErrorState";
import { LoadingState } from "../common/LoadingState";
import { getBranches, getHistory, getQueueEntry } from "../../services/queue";
import { getNotifications } from "../../services/notifications";
import { useAuthStore } from "../../store/authStore";
import { useQueueWebSocket } from "../../hooks/useQueueWebSocket";
import { formatQueueNumber } from "../../utils/queueNumber";

export function CustomerHomeSummary() {
  const token = useAuthStore((state) => state.token);
  const user = useAuthStore((state) => state.user);
  const isCustomer = Boolean(token && user?.role === "customer");
  const history = useQuery({
    queryKey: ["queue-history"],
    queryFn: () => getHistory(1, 50),
    enabled: isCustomer,
    refetchInterval: isCustomer ? 30_000 : false,
  });
  const notifications = useQuery({
    queryKey: ["notifications"],
    queryFn: () => getNotifications(1),
    enabled: isCustomer,
    refetchInterval: isCustomer ? 30_000 : false,
  });
  const branches = useQuery({
    queryKey: ["branches", "home"],
    queryFn: () => getBranches(),
    enabled: isCustomer,
    staleTime: 60_000,
  });
  const activeEntry = history.data?.items.find((item) =>
    ["waiting", "called", "serving"].includes(item.status),
  );
  const position = useQuery({
    queryKey: ["queue-entry", activeEntry?.entry_id],
    queryFn: () => getQueueEntry(activeEntry!.entry_id),
    enabled: isCustomer && Boolean(activeEntry),
  });
  useQueueWebSocket(position.data?.queue_id, token ?? undefined);

  if (!isCustomer) return null;

  return (
    <section aria-labelledby="customer-dashboard-heading" className="mb-16">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm font-bold uppercase tracking-[0.18em] text-emerald-800">
            Your account
          </p>
          <h2
            className="mt-2 text-3xl font-black tracking-tight text-ink"
            id="customer-dashboard-heading"
          >
            Welcome back, {user?.full_name.split(" ")[0]}.
          </h2>
        </div>
        <Link
          className="inline-flex items-center gap-2 text-sm font-bold text-emerald-800 hover:text-emerald-950"
          to="/history"
        >
          Queue history
          <ArrowRight aria-hidden="true" size={16} />
        </Link>
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
        <article className="rounded-3xl border border-ink/10 bg-white p-5 sm:p-6">
          <div className="flex items-center gap-3">
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-emerald-50 text-emerald-800">
              <TicketCheck aria-hidden="true" size={20} />
            </span>
            <div>
              <h3 className="font-black text-ink">Your active queue</h3>
              <p className="text-sm text-ink/55">Live status for your current place</p>
            </div>
          </div>
          {history.isLoading && <LoadingState label="Checking your queue..." />}
          {history.isError && (
            <div className="mt-4">
              <ErrorState
                message="Unable to load your queue history."
                onRetry={() => void history.refetch()}
              />
            </div>
          )}
          {history.data && !activeEntry && (
            <EmptyState
              title="No active queue right now"
              message="Browse services and join when you are ready."
              action={
                <Link
                  className="inline-flex items-center gap-2 rounded-full bg-ink px-4 py-2 text-sm font-bold text-white"
                  to="/services"
                >
                  Browse services
                  <ArrowRight aria-hidden="true" size={15} />
                </Link>
              }
            />
          )}
          {activeEntry && position.isLoading && (
            <LoadingState label="Refreshing your queue position..." />
          )}
          {activeEntry && position.isError && (
            <div className="mt-4">
              <ErrorState
                message="Unable to load your current queue position."
                onRetry={() => void position.refetch()}
              />
            </div>
          )}
          {activeEntry && position.data && (
            <div className="mt-5 rounded-2xl bg-ink p-5 text-white">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-sm text-white/65">{activeEntry.queue_name}</p>
                  <p className="mt-1 text-3xl font-black">
                    {formatQueueNumber(
                      position.data.queue_prefix,
                      position.data.queue_number,
                    )}
                  </p>
                </div>
                <span className="rounded-full bg-white/10 px-3 py-1.5 text-xs font-bold capitalize">
                  {position.data.status}
                </span>
              </div>
              <div className="mt-4 grid grid-cols-2 gap-3">
                <div className="rounded-xl bg-white/10 p-3">
                  <p className="text-xs text-white/60">People ahead</p>
                  <p className="mt-1 text-xl font-black">{position.data.people_ahead}</p>
                </div>
                <div className="rounded-xl bg-white/10 p-3">
                  <p className="text-xs text-white/60">Estimated wait</p>
                  <p className="mt-1 text-xl font-black">
                    {position.data.estimated_wait_minutes} min
                  </p>
                </div>
              </div>
              <Link
                className="mt-4 inline-flex items-center gap-2 text-sm font-bold text-mint hover:text-lime-200"
                to={`/queue/${activeEntry.entry_id}`}
              >
                Open live ticket
                <ArrowRight aria-hidden="true" size={16} />
              </Link>
            </div>
          )}
        </article>

        <div className="grid gap-4">
          <Link
            className="flex items-center justify-between gap-4 rounded-3xl border border-ink/10 bg-white p-5 transition hover:shadow-md"
            to="/notifications"
          >
            <span className="flex items-center gap-3">
              <span className="grid h-10 w-10 place-items-center rounded-xl bg-amber-50 text-amber-900">
                <Bell aria-hidden="true" size={20} />
              </span>
              <span>
                <span className="block font-black text-ink">Notifications</span>
                <span className="block text-sm text-ink/55">
                  {notifications.isLoading
                    ? "Loading your updates..."
                    : notifications.isError
                      ? "Updates are temporarily unavailable."
                      : `${notifications.data?.unread_count ?? 0} unread`}
                </span>
              </span>
            </span>
            <ArrowRight aria-hidden="true" className="shrink-0 text-ink/50" size={17} />
          </Link>

          <article className="rounded-3xl border border-ink/10 bg-white p-5">
            <div className="flex items-center gap-3">
              <span className="grid h-10 w-10 place-items-center rounded-xl bg-sky-50 text-sky-900">
                <MapPin aria-hidden="true" size={20} />
              </span>
              <div>
                <h3 className="font-black text-ink">Available branches</h3>
                <p className="text-sm text-ink/55">Choose a location to get started</p>
              </div>
            </div>
            {branches.isLoading && <LoadingState label="Loading branches..." />}
            {branches.isError && (
              <div className="mt-3">
                <ErrorState
                  message="Unable to load branches."
                  onRetry={() => void branches.refetch()}
                />
              </div>
            )}
            {branches.data?.length === 0 && (
              <p className="mt-4 rounded-xl bg-slate-50 p-3 text-sm text-ink/60">
                No active branches are available yet.
              </p>
            )}
            {branches.data && branches.data.length > 0 && (
              <ul className="mt-3 divide-y divide-ink/10">
                {branches.data.slice(0, 3).map((branch) => (
                  <li className="py-2.5 first:pt-1 last:pb-0" key={branch.id}>
                    <Link
                      className="block font-semibold text-ink hover:text-emerald-800"
                      to={`/services?branch_id=${encodeURIComponent(branch.id)}`}
                    >
                      {branch.name}
                    </Link>
                    {branch.address && (
                      <span className="mt-0.5 block text-xs text-ink/55">
                        {branch.address}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </article>
        </div>
      </div>

      {history.data && history.data.items.length > 0 && (
        <article className="mt-4 rounded-3xl border border-ink/10 bg-white p-5 sm:p-6">
          <div className="flex items-center justify-between gap-3">
            <h3 className="font-black text-ink">Recent queue activity</h3>
            <Link className="text-sm font-bold text-emerald-800" to="/history">
              View history
            </Link>
          </div>
          <ul className="mt-3 divide-y divide-ink/10">
            {history.data.items.slice(0, 3).map((entry) => (
              <li
                className="flex flex-wrap items-center justify-between gap-2 py-3 first:pt-1 last:pb-0"
                key={entry.entry_id}
              >
                <div>
                  <p className="font-semibold text-ink">{entry.queue_name}</p>
                  <p className="text-xs text-ink/55">
                    Joined {new Date(entry.joined_at).toLocaleString()}
                  </p>
                </div>
                <span className="rounded-full bg-ink/5 px-3 py-1 text-xs font-bold capitalize text-ink">
                  {entry.status}
                </span>
              </li>
            ))}
          </ul>
        </article>
      )}
    </section>
  );
}
