import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { Button } from "../../components/common/Button";
import { EmptyState } from "../../components/common/EmptyState";
import { ErrorState } from "../../components/common/ErrorState";
import { LoadingState } from "../../components/common/LoadingState";
import { PageContainer } from "../../components/common/PageContainer";
import {
  getNotificationPreferences,
  getNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  updateNotificationPreferences,
} from "../../services/notifications";
import type { NotificationPreferences } from "../../services/notifications";
import { captureProductEvent } from "../../observability";

const preferenceOptions: { key: keyof Omit<NotificationPreferences, "enabled">; label: string }[] = [
  { key: "joined", label: "When I join a queue" },
  { key: "called", label: "When I am called" },
  { key: "approaching", label: "When my turn is approaching" },
  { key: "completed", label: "When service is completed" },
  { key: "queue_updates", label: "When a queue is paused, resumed, or closed" },
];

export function NotificationsPage() {
  const client = useQueryClient();
  useEffect(() => {
    captureProductEvent("notification_opened");
  }, []);
  const query = useQuery({
    queryKey: ["notifications"],
    queryFn: () => getNotifications(),
  });
  const preferences = useQuery({
    queryKey: ["notification-preferences"],
    queryFn: getNotificationPreferences,
  });
  const refreshNotifications = () => void client.invalidateQueries({ queryKey: ["notifications"] });
  const mark = useMutation({ mutationFn: markNotificationRead, onSuccess: refreshNotifications });
  const markAll = useMutation({ mutationFn: markAllNotificationsRead, onSuccess: refreshNotifications });
  const savePreferences = useMutation({
    mutationFn: updateNotificationPreferences,
    onSuccess: () => void client.invalidateQueries({ queryKey: ["notification-preferences"] }),
  });

  if (query.isLoading) return <LoadingState />;
  if (query.isError || !query.data) return <ErrorState message="Unable to load notifications." />;

  const savePreference = (key: keyof NotificationPreferences, value: boolean) => {
    if (preferences.data) savePreferences.mutate({ ...preferences.data, [key]: value });
  };

  return (
    <PageContainer className="max-w-3xl py-10">
      <div className="flex items-center justify-between">
        <h1 className="text-4xl font-black">Notifications</h1>
        <Button
          variant="secondary"
          onClick={() => markAll.mutate()}
          disabled={!query.data.unread_count || markAll.isPending}
        >
          Mark all read
        </Button>
      </div>
      {preferences.data && (
        <fieldset className="mt-5 rounded-2xl border bg-white p-4">
          <legend className="px-2 font-bold">Notification preferences</legend>
          <label className="flex gap-2 text-sm">
            <input
              type="checkbox"
              checked={preferences.data.enabled}
              onChange={(event) => savePreference("enabled", event.target.checked)}
            />
            Enable in-app notifications
          </label>
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {preferenceOptions.map(({ key, label }) => (
              <label key={key} className="flex gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={preferences.data[key]}
                  disabled={!preferences.data.enabled || savePreferences.isPending}
                  onChange={(event) => savePreference(key, event.target.checked)}
                />
                {label}
              </label>
            ))}
          </div>
          <p className="mt-3 text-xs text-ink/60">
            Browser notifications are optional and can be enabled from your queue ticket.
          </p>
        </fieldset>
      )}
      <div className="mt-6 space-y-3">
        {query.data.items.length === 0 && (
          <EmptyState title="No notifications yet" message="Queue updates will appear here." />
        )}
        {query.data.items.map((item) => (
          <article
            key={item.id}
            className={`rounded-2xl border p-5 ${
              item.is_read ? "border-ink/10 bg-white" : "border-emerald-300 bg-emerald-50"
            }`}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="font-black">{item.title}</p>
                <p className="mt-1 text-sm text-ink/70">{item.message}</p>
                <p className="mt-2 text-xs text-ink/50">
                  {new Date(item.created_at).toLocaleString()}
                </p>
              </div>
              {!item.is_read && (
                <Button
                  variant="secondary"
                  onClick={() => mark.mutate(item.id)}
                  disabled={mark.isPending}
                >
                  Mark read
                </Button>
              )}
            </div>
            {item.queue_entry_id && (
              <Link
                className="mt-3 inline-block text-sm font-bold text-emerald-800"
                to={`/queue/${item.queue_entry_id}`}
              >
                View queue
              </Link>
            )}
          </article>
        ))}
      </div>
    </PageContainer>
  );
}
