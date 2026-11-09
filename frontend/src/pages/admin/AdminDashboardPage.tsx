import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { PageContainer } from "../../components/common/PageContainer";
import { LoadingState } from "../../components/common/LoadingState";
import { ErrorState } from "../../components/common/ErrorState";
import { useAuthStore } from "../../store/authStore";
import { downloadAdminQueueReport, getAdminAnalytics } from "../../services/admin";
import { StatsCard } from "../../components/staff/StatsCard";
import { QueueRequestReviewPanel } from "../../components/queue/QueueRequestReviewPanel";
import { getAdminQueueOptions } from "../../services/queueRequests";

export function AdminDashboardPage() {
  const token = useAuthStore((s) => s.token)!;
  const queryClient = useQueryClient();
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [appliedRange, setAppliedRange] = useState({ start: "", end: "" });
  const [rangeError, setRangeError] = useState("");
  const [reportState, setReportState] = useState<"idle" | "loading" | "error">("idle");
  useEffect(() => {
    if (!("BroadcastChannel" in window)) return;
    const channel = new BroadcastChannel("queueless:queue-events");
    channel.onmessage = () => {
      void queryClient.invalidateQueries({ queryKey: ["admin-analytics"] });
      void queryClient.invalidateQueries({ queryKey: ["admin", "queue-options"] });
      void queryClient.invalidateQueries({ queryKey: ["queue-requests"] });
    };
    return () => channel.close();
  }, [queryClient]);
  const query = useQuery({
    queryKey: ["admin-analytics", appliedRange.start, appliedRange.end],
    queryFn: () =>
      getAdminAnalytics(token, appliedRange.start, appliedRange.end),
    refetchInterval: 10_000,
  });
  const queues = useQuery({
    queryKey: ["admin", "queue-options"],
    queryFn: () => getAdminQueueOptions(token),
    refetchInterval: 10_000,
  });
  if (query.isLoading) return <LoadingState />;
  if (!query.data) {
    return (
      <ErrorState
        message="Unable to load analytics."
        onRetry={() => void query.refetch()}
      />
    );
  }
  const data = query.data;
  const chart = [{ name: "Completed", value: data.completed_entries }, { name: "Waiting", value: data.waiting_entries }];
  const applyDateRange = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (startDate && endDate && startDate > endDate) {
      setRangeError("Start date must be on or before the end date.");
      return;
    }
    setRangeError("");
    setAppliedRange({ start: startDate, end: endDate });
  };
  const downloadReport = async () => {
    setReportState("loading");
    try {
      const report = await downloadAdminQueueReport(
        token,
        appliedRange.start,
        appliedRange.end,
      );
      const url = URL.createObjectURL(report);
      const link = document.createElement("a");
      link.href = url;
      link.download = "queueless-queue-report.csv";
      document.body.append(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 0);
      setReportState("idle");
    } catch {
      setReportState("error");
    }
  };
  return <PageContainer className="py-10"><div className="flex flex-wrap items-end justify-between gap-3"><h1 className="text-4xl font-black">Admin dashboard</h1><p className="text-sm text-ink/60" aria-live="polite">Updated {new Date(query.dataUpdatedAt).toLocaleTimeString()}</p></div>
    <form className="mt-5 flex flex-wrap items-end gap-3 rounded-2xl border border-ink/10 bg-white p-4" onSubmit={applyDateRange}>
      <label className="grid gap-1 text-sm font-semibold">From<input aria-label="Analytics start date" className="rounded-lg border p-2" type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)}/></label>
      <label className="grid gap-1 text-sm font-semibold">To<input aria-label="Analytics end date" className="rounded-lg border p-2" type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)}/></label>
      <button className="rounded-full bg-ink px-4 py-2 text-sm font-bold text-white" type="submit">Apply dates</button>
      {(appliedRange.start || appliedRange.end) && <button className="rounded-full border px-4 py-2 text-sm font-bold" type="button" onClick={() => { setStartDate(""); setEndDate(""); setRangeError(""); setAppliedRange({ start: "", end: "" }); }}>Clear dates</button>}
      {rangeError && <p className="w-full text-sm text-red-700" role="alert">{rangeError}</p>}
    </form>
    <div className="mt-4 flex flex-wrap items-center gap-3">
      <button className="rounded-full border border-ink/20 bg-white px-4 py-2 text-sm font-bold disabled:opacity-60" type="button" disabled={reportState === "loading"} onClick={() => void downloadReport()}>
        {reportState === "loading" ? "Preparing report..." : "Download queue report (CSV)"}
      </button>
      {reportState === "error" && <p className="text-sm text-red-700" role="alert">The report could not be downloaded. Try again.</p>}
      <p className="text-sm text-ink/60">Includes queue entries and the selected date range.</p>
    </div>
    {query.isError && <p className="mt-4 rounded-xl bg-amber-50 p-3 text-sm text-amber-900" role="alert">Live analytics could not refresh. Showing the last loaded data. <button className="ml-2 font-bold underline" onClick={() => void query.refetch()}>Retry</button></p>}
    <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4"><StatsCard label="Completed today" value={data.customers_served_today}/><StatsCard label="Waiting" value={data.customers_waiting}/><StatsCard label="Average wait (min)" value={data.average_waiting_time}/><StatsCard label="Avg service (min)" value={data.average_service_time}/></div>
    <div className="mt-8 grid gap-6 lg:grid-cols-2"><div className="rounded-2xl bg-white p-6"><h2 className="font-black">{appliedRange.start || appliedRange.end ? "Queue volume for selected dates" : "Queue volume"}</h2><div className="h-64"><ResponsiveContainer width="100%" height="100%"><BarChart data={chart}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="name"/><YAxis allowDecimals={false}/><Tooltip/><Bar dataKey="value" fill="#12352f"/></BarChart></ResponsiveContainer></div></div>
    <div className="rounded-2xl bg-white p-6"><h2 className="font-black">Rates</h2><dl className="mt-4 space-y-3 text-sm"><div className="flex justify-between"><dt>Completion</dt><dd>{data.completion_rate}%</dd></div><div className="flex justify-between"><dt>Skip</dt><dd>{data.skip_rate}%</dd></div><div className="flex justify-between"><dt>Cancellation</dt><dd>{data.cancellation_rate}%</dd></div><div className="flex justify-between"><dt>Busiest service</dt><dd>{data.busiest_service?.name ?? "No data"}</dd></div><div className="flex justify-between"><dt>Busiest hour</dt><dd>{data.busiest_hour ? `${data.busiest_hour.hour}:00` : "No data"}</dd></div></dl></div></div>
    {queues.isLoading && <LoadingState label="Loading queues for request assignment..." />}
    {queues.isError && <ErrorState message="Unable to load queues for request assignment." onRetry={() => void queues.refetch()} />}
    {queues.data && <QueueRequestReviewPanel queues={queues.data.items} />}
  </PageContainer>;
}
