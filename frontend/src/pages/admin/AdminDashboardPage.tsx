import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { PageContainer } from "../../components/common/PageContainer";
import { LoadingState } from "../../components/common/LoadingState";
import { ErrorState } from "../../components/common/ErrorState";
import { useAuthStore } from "../../store/authStore";
import { getAdminAnalytics } from "../../services/admin";
import { StatsCard } from "../../components/staff/StatsCard";

export function AdminDashboardPage() {
  const token = useAuthStore((s) => s.token)!;
  const queryClient = useQueryClient();
  useEffect(() => {
    if (!("BroadcastChannel" in window)) return;
    const channel = new BroadcastChannel("queueless:queue-events");
    channel.onmessage = () =>
      void queryClient.invalidateQueries({ queryKey: ["admin-analytics"] });
    return () => channel.close();
  }, [queryClient]);
  const query = useQuery({ queryKey: ["admin-analytics"], queryFn: () => getAdminAnalytics(token), refetchInterval: 30000 });
  if (query.isLoading) return <LoadingState />;
  if (query.isError || !query.data) return <ErrorState message="Unable to load analytics." />;
  const data = query.data;
  const chart = [{ name: "Completed", value: data.customers_served_today }, { name: "Waiting", value: data.customers_waiting }];
  return <PageContainer className="py-10"><h1 className="text-4xl font-black">Admin dashboard</h1>
    <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4"><StatsCard label="Completed today" value={data.customers_served_today}/><StatsCard label="Waiting" value={data.customers_waiting}/><StatsCard label="Average wait (min)" value={data.average_waiting_time}/><StatsCard label="Avg service (min)" value={data.average_service_time}/></div>
    <div className="mt-8 grid gap-6 lg:grid-cols-2"><div className="rounded-2xl bg-white p-6"><h2 className="font-black">Queue volume</h2><div className="h-64"><ResponsiveContainer width="100%" height="100%"><BarChart data={chart}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="name"/><YAxis allowDecimals={false}/><Tooltip/><Bar dataKey="value" fill="#12352f"/></BarChart></ResponsiveContainer></div></div>
    <div className="rounded-2xl bg-white p-6"><h2 className="font-black">Rates</h2><dl className="mt-4 space-y-3 text-sm"><div className="flex justify-between"><dt>Completion</dt><dd>{data.completion_rate}%</dd></div><div className="flex justify-between"><dt>Skip</dt><dd>{data.skip_rate}%</dd></div><div className="flex justify-between"><dt>Cancellation</dt><dd>{data.cancellation_rate}%</dd></div><div className="flex justify-between"><dt>Busiest service</dt><dd>{data.busiest_service?.name ?? "No data"}</dd></div><div className="flex justify-between"><dt>Busiest hour</dt><dd>{data.busiest_hour ? `${data.busiest_hour.hour}:00` : "No data"}</dd></div></dl></div></div></PageContainer>;
}
