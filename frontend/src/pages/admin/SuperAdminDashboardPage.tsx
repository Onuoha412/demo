import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ErrorState } from "../../components/common/ErrorState";
import { LoadingState } from "../../components/common/LoadingState";
import { PageContainer } from "../../components/common/PageContainer";
import { SuperAdminInitialSetupWizard } from "../../components/admin/SuperAdminInitialSetupWizard";
import { StatsCard } from "../../components/staff/StatsCard";
import {
  createSuperAdminBackup,
  getSuperAdminDashboard,
  getSuperAdminBackups,
  getSuperAdminHealth,
  getSuperAdminWebSocketTicket,
} from "../../services/superAdmin";
import { WS_BASE } from "../../services/api";
import { useAuthStore } from "../../store/authStore";

const sections = [
  ["users", "Users"],
  ["organizations", "Organizations"],
  ["branches", "Branches"],
  ["services", "Services"],
  ["counters", "Counters"],
  ["queues", "Queues"],
] as const;

export function SuperAdminDashboardPage() {
  const token = useAuthStore((state) => state.token)!;
  const queryClient = useQueryClient();
  const [initialSetupCompleted, setInitialSetupCompleted] = useState(false);
  const [realtimeStatus, setRealtimeStatus] = useState<
    "connecting" | "connected" | "reconnecting"
  >("connecting");
  useEffect(() => {
    let stopped = false;
    let socket: WebSocket | null = null;
    let retryTimer: number | undefined;
    let retryCount = 0;

    const reconnect = () => {
      if (stopped) return;
      setRealtimeStatus("reconnecting");
      const delay = Math.min(30_000, 1_000 * 2 ** retryCount++);
      retryTimer = window.setTimeout(
        () => void connect(),
        delay + Math.random() * delay * 0.25,
      );
    };
    const connect = async () => {
      setRealtimeStatus("connecting");
      try {
        const { ticket } = await getSuperAdminWebSocketTicket(token);
        if (stopped) return;
        socket = new WebSocket(
          `${WS_BASE}/ws/super-admin?${new URLSearchParams({ ticket })}`,
        );
        socket.onopen = () => {
          retryCount = 0;
          setRealtimeStatus("connected");
          void queryClient.invalidateQueries({
            queryKey: ["super-admin-dashboard"],
          });
        };
        socket.onmessage = () => {
          void queryClient.invalidateQueries({
            queryKey: ["super-admin-dashboard"],
          });
        };
        socket.onclose = () => reconnect();
        socket.onerror = () => {
          setRealtimeStatus("reconnecting");
          socket?.close();
        };
      } catch {
        reconnect();
      }
    };

    void connect();
    return () => {
      stopped = true;
      if (retryTimer !== undefined) window.clearTimeout(retryTimer);
      socket?.close();
    };
  }, [queryClient, token]);
  const dashboard = useQuery({
    queryKey: ["super-admin-dashboard"],
    queryFn: () => getSuperAdminDashboard(token),
    refetchInterval: 30_000,
  });
  const health = useQuery({
    queryKey: ["super-admin-health"],
    queryFn: () => getSuperAdminHealth(token),
    refetchInterval: 30_000,
  });
  const backups = useQuery({
    queryKey: ["super-admin-backups"],
    queryFn: () => getSuperAdminBackups(token),
    refetchInterval: 60_000,
  });
  const createBackup = useMutation({
    mutationFn: () => createSuperAdminBackup(token),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["super-admin-backups"] });
      void queryClient.invalidateQueries({ queryKey: ["super-admin-health"] });
    },
  });

  if (dashboard.isLoading) return <LoadingState />;
  if (!dashboard.data) {
    return (
      <ErrorState
        message="Unable to load the Super Admin overview."
        onRetry={() => void dashboard.refetch()}
      />
    );
  }

  const data = dashboard.data;
  const usersTotal = Object.values(data.users).reduce(
    (total, count) => total + count,
    0,
  );

  return (
    <PageContainer className="py-10">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm font-bold uppercase tracking-wide text-emerald-800">
            Global control center
          </p>
          <h1 className="text-4xl font-black">Super Admin</h1>
        </div>
        <p className="text-sm text-ink/60" aria-live="polite">
          Live totals · updated {new Date(dashboard.dataUpdatedAt).toLocaleTimeString()}
        </p>
        <p className="text-sm text-ink/60" aria-live="polite">
          Platform events: {realtimeStatus}
        </p>
      </div>

      {dashboard.isError && (
        <p className="mt-4 rounded-xl bg-amber-50 p-3 text-sm text-amber-900" role="alert">
          The overview could not refresh. Showing the most recently loaded data.{" "}
          <button
            className="font-bold underline"
            onClick={() => void dashboard.refetch()}
          >
            Retry
          </button>
        </p>
      )}

      {(data.organizations === 0 || initialSetupCompleted) && (
        <SuperAdminInitialSetupWizard
          token={token}
          onComplete={() => setInitialSetupCompleted(true)}
        />
      )}

      <section aria-label="Platform totals" className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatsCard label="All users" value={usersTotal} />
        <StatsCard label="Customers" value={data.users.customer ?? 0} />
        <StatsCard label="Staff" value={data.users.staff ?? 0} />
        <StatsCard label="Admins" value={data.users.admin ?? 0} />
        <StatsCard label="Super Admins" value={data.users.super_admin ?? 0} />
        <StatsCard label="Organizations" value={data.organizations} />
        <StatsCard label="Branches" value={data.branches} />
        <StatsCard label="Services" value={data.services} />
        <StatsCard label="Counters" value={data.counters} />
        <StatsCard label="Waiting" value={data.queues.waiting ?? 0} />
        <StatsCard label="Serving" value={data.queues.serving ?? 0} />
        <StatsCard label="Completed" value={data.queues.completed ?? 0} />
        <StatsCard label="Skipped" value={data.queues.skipped ?? 0} />
        <StatsCard label="Cancelled" value={data.queues.cancelled ?? 0} />
      </section>

      <section className="mt-8 rounded-2xl bg-white p-6">
        <h2 className="text-xl font-black">Manage QueueLess</h2>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {sections.map(([path, label]) => (
            <Link
              key={path}
              to={`/super-admin/${path}`}
              className="rounded-xl border border-ink/10 p-4 font-semibold transition hover:border-emerald-700 hover:bg-emerald-50"
            >
              Manage {label.toLowerCase()}
            </Link>
          ))}
          <Link
            to="/super-admin/audit-logs"
            className="rounded-xl border border-ink/10 p-4 font-semibold transition hover:border-emerald-700 hover:bg-emerald-50"
          >
            Security audit log
          </Link>
          <Link
            to="/super-admin/operations"
            className="rounded-xl border border-ink/10 p-4 font-semibold transition hover:border-emerald-700 hover:bg-emerald-50"
          >
            Announcements &amp; system settings
          </Link>
        </div>
      </section>

      <section className="mt-8 grid gap-6 lg:grid-cols-2">
        <div className="rounded-2xl bg-white p-6">
          <h2 className="text-xl font-black">Application health</h2>
          {health.isLoading ? (
            <LoadingState label="Checking API and database..." />
          ) : health.data ? (
            <dl className="mt-4 space-y-3 text-sm">
              <div className="flex justify-between gap-4">
                <dt>API</dt>
                <dd className="font-semibold">{health.data.api}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt>Database</dt>
                <dd className="font-semibold">{health.data.database}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt>Backup monitoring</dt>
                <dd className="font-semibold">{health.data.backup_monitoring}</dd>
              </div>
            </dl>
          ) : (
            <ErrorState
              message="Health status is unavailable."
              onRetry={() => void health.refetch()}
            />
          )}
          <div className="mt-6 border-t border-ink/10 pt-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="font-bold">Backup inventory</h3>
                {backups.data && (
                  <p className="mt-1 text-xs text-ink/60">
                    {backups.data.length} recent verified snapshot
                    {backups.data.length === 1 ? "" : "s"}
                  </p>
                )}
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  className="rounded-full border border-ink/20 px-4 py-2 text-sm font-bold disabled:opacity-50"
                  disabled={backups.isFetching}
                  onClick={() => void backups.refetch()}
                >
                  {backups.isFetching ? "Refreshing..." : "Refresh inventory"}
                </button>
                <button
                  className="rounded-full bg-ink px-4 py-2 text-sm font-bold text-white disabled:opacity-50"
                  disabled={createBackup.isPending}
                  onClick={() => createBackup.mutate()}
                >
                  {createBackup.isPending ? "Creating..." : "Create backup"}
                </button>
              </div>
            </div>
            <p className="mt-2 text-xs text-ink/60">
              Restore is an offline CLI operation; stop all API processes before restoring.
            </p>
            {backups.isLoading && <LoadingState label="Loading backup snapshots..." />}
            {backups.isError && (
              <p role="alert" className="mt-3 text-sm text-red-800">
                Backup inventory is unavailable.
              </p>
            )}
            {backups.data && backups.data.length === 0 && (
              <p className="mt-3 text-sm text-ink/60">No verified snapshots yet.</p>
            )}
            {backups.data && backups.data.length > 0 && (
              <ul aria-label="Verified database backups" className="mt-3 divide-y divide-ink/10">
                {backups.data.map((backup) => (
                  <li key={backup.filename} className="py-2 text-sm">
                    <span className="font-semibold">{backup.filename}</span>
                    <span className="block text-xs text-ink/60">
                      {new Date(backup.created_at).toLocaleString()} ·{" "}
                      {(backup.size_bytes / 1024 / 1024).toFixed(2)} MB
                    </span>
                  </li>
                ))}
              </ul>
            )}
            {createBackup.isError && (
              <p role="alert" className="mt-3 text-sm text-red-800">
                Backup creation failed. Reauthenticate if your admin session is no longer recent.
              </p>
            )}
          </div>
        </div>
        <div className="rounded-2xl bg-white p-6">
          <div className="flex items-center justify-between gap-4">
            <h2 className="text-xl font-black">Recent security events</h2>
            <Link
              className="text-sm font-bold text-emerald-800 underline"
              to="/super-admin/audit-logs"
            >
              View all
            </Link>
          </div>
          {data.recent_events.length ? (
            <ul className="mt-4 divide-y divide-ink/10">
              {data.recent_events.slice(0, 6).map((event) => (
                <li key={event.id} className="py-3 text-sm">
                  <p className="font-semibold">{event.action.replaceAll(".", " ")}</p>
                  <p className="mt-1 text-ink/60">
                    {event.actor_email ?? "System"} ·{" "}
                    {new Date(event.created_at).toLocaleString()}
                  </p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-4 text-sm text-ink/60">
              Security events will appear as administrative actions occur.
            </p>
          )}
        </div>
      </section>
    </PageContainer>
  );
}