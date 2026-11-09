import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { ErrorState } from "../../components/common/ErrorState";
import { LoadingState } from "../../components/common/LoadingState";
import { PageContainer } from "../../components/common/PageContainer";
import {
  createPlatformAnnouncement,
  getPlatformAnnouncements,
  getPlatformSettings,
  setAnnouncementPublished,
  updatePlatformSettings,
  updatePlatformAnnouncement,
  type AnnouncementInput,
  type PlatformSettings,
} from "../../services/operations";
import { useAuthStore } from "../../store/authStore";

const emptyAnnouncement: AnnouncementInput = {
  title: "",
  body: "",
  audience: "all",
  expires_at: null,
};

export function SuperAdminOperationsPage() {
  const token = useAuthStore((state) => state.token)!;
  const queryClient = useQueryClient();
  const [announcement, setAnnouncement] = useState(emptyAnnouncement);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [settingsDraft, setSettingsDraft] = useState<
    Pick<PlatformSettings, "maintenance_mode" | "maintenance_message"> | null
  >(null);
  const [notice, setNotice] = useState("");
  const announcements = useQuery({
    queryKey: ["platform-announcements"],
    queryFn: () => getPlatformAnnouncements(token),
  });
  const settings = useQuery({
    queryKey: ["platform-settings"],
    queryFn: () => getPlatformSettings(token),
  });

  const settingsValue = settingsDraft ?? {
    maintenance_mode: settings.data?.maintenance_mode ?? false,
    maintenance_message: settings.data?.maintenance_message ?? "",
  };

  const refreshAnnouncements = () => {
    void queryClient.invalidateQueries({ queryKey: ["platform-announcements"] });
    void queryClient.invalidateQueries({ queryKey: ["announcements", "published"] });
  };
  const createAnnouncement = useMutation({
    mutationFn: () =>
      editingId
        ? updatePlatformAnnouncement(editingId, announcement, token)
        : createPlatformAnnouncement(announcement, token),
    onSuccess: () => {
      setAnnouncement(emptyAnnouncement);
      setEditingId(null);
      setNotice(editingId ? "Announcement updated." : "Announcement saved as a draft.");
      refreshAnnouncements();
    },
  });
  const publishAnnouncement = useMutation({
    mutationFn: ({ id, published }: { id: string; published: boolean }) =>
      setAnnouncementPublished(id, published, token),
    onSuccess: (_result, variables) => {
      setNotice(variables.published ? "Announcement published." : "Announcement unpublished.");
      refreshAnnouncements();
    },
  });
  const saveSettings = useMutation({
    mutationFn: () =>
      updatePlatformSettings(
        settingsValue,
        token,
      ),
    onSuccess: () => {
      setNotice("Platform settings saved.");
      void queryClient.invalidateQueries({ queryKey: ["platform-settings"] });
      void queryClient.invalidateQueries({ queryKey: ["platform-health"] });
    },
  });

  return (
    <PageContainer className="py-10">
      <p className="text-sm font-bold uppercase tracking-wide text-emerald-800">
        Global platform controls
      </p>
      <h1 className="mt-2 text-4xl font-black">Announcements &amp; operations</h1>
      <p className="mt-3 max-w-3xl text-ink/70">
        Publish audience-specific service announcements and control maintenance access.
        Changes are recorded in the security audit log.
      </p>
      {notice && <p className="mt-4 text-sm font-semibold text-emerald-900" role="status">{notice}</p>}

      <section className="mt-8 grid gap-6 lg:grid-cols-2">
        <form
          className="space-y-4 rounded-2xl bg-white p-6"
          onSubmit={(event) => {
            event.preventDefault();
            setNotice("");
            createAnnouncement.mutate();
          }}
        >
          <h2 className="text-xl font-black">
            {editingId ? "Edit announcement" : "Create announcement"}
          </h2>
          <label className="block text-sm font-semibold">
            Title
            <input
              className="mt-1 w-full rounded-lg border border-ink/20 px-3 py-2"
              maxLength={160}
              onChange={(event) =>
                setAnnouncement({ ...announcement, title: event.target.value })
              }
              required
              value={announcement.title}
            />
          </label>
          <label className="block text-sm font-semibold">
            Message
            <textarea
              className="mt-1 min-h-32 w-full rounded-lg border border-ink/20 px-3 py-2"
              maxLength={5000}
              onChange={(event) =>
                setAnnouncement({ ...announcement, body: event.target.value })
              }
              required
              value={announcement.body}
            />
          </label>
          <label className="block text-sm font-semibold">
            Audience
            <select
              className="mt-1 w-full rounded-lg border border-ink/20 px-3 py-2"
              onChange={(event) =>
                setAnnouncement({
                  ...announcement,
                  audience: event.target.value as AnnouncementInput["audience"],
                })
              }
              value={announcement.audience}
            >
              <option value="all">Customers and staff</option>
              <option value="customer">Customers</option>
              <option value="staff">Staff</option>
            </select>
          </label>
          <button
            className="rounded-full bg-ink px-5 py-3 font-bold text-white disabled:opacity-50"
            disabled={createAnnouncement.isPending}
            type="submit"
          >
            {createAnnouncement.isPending
              ? "Saving..."
              : editingId
                ? "Save changes"
                : "Save draft"}
          </button>
          {editingId && (
            <button
              className="ml-3 rounded-full border border-ink/20 px-5 py-3 font-bold"
              onClick={() => {
                setEditingId(null);
                setAnnouncement(emptyAnnouncement);
              }}
              type="button"
            >
              Cancel edit
            </button>
          )}
          {createAnnouncement.isError && (
            <p className="text-sm text-red-800" role="alert">
              {createAnnouncement.error.message}
            </p>
          )}
        </form>

        <form
          className="space-y-4 rounded-2xl bg-white p-6"
          onSubmit={(event) => {
            event.preventDefault();
            setNotice("");
            saveSettings.mutate();
          }}
        >
          <h2 className="text-xl font-black">System settings</h2>
          {settings.isLoading && <LoadingState label="Loading platform settings..." />}
          {settings.isError && (
            <ErrorState
              message="Platform settings could not be loaded."
              onRetry={() => void settings.refetch()}
            />
          )}
          <label className="flex items-start gap-3 text-sm font-semibold">
            <input
              checked={settingsValue.maintenance_mode}
              className="mt-1"
              onChange={(event) =>
                setSettingsDraft({
                  ...settingsValue,
                  maintenance_mode: event.target.checked,
                })
              }
              type="checkbox"
            />
            Enable maintenance mode (non-admin API requests will receive HTTP 503)
          </label>
          <label className="block text-sm font-semibold">
            Maintenance message
            <textarea
              className="mt-1 min-h-24 w-full rounded-lg border border-ink/20 px-3 py-2"
              maxLength={500}
              onChange={(event) =>
                setSettingsDraft({
                  ...settingsValue,
                  maintenance_message: event.target.value,
                })
              }
              required
              value={settingsValue.maintenance_message}
            />
          </label>
          <button
            className="rounded-full bg-emerald-800 px-5 py-3 font-bold text-white disabled:opacity-50"
            disabled={saveSettings.isPending || settings.isLoading || settings.isError}
            type="submit"
          >
            {saveSettings.isPending ? "Saving..." : "Save system settings"}
          </button>
          {saveSettings.isError && (
            <p className="text-sm text-red-800" role="alert">{saveSettings.error.message}</p>
          )}
          <p className="text-xs text-ink/60">
            Health checks and Super Admin controls remain available during maintenance.
          </p>
        </form>
      </section>

      <section className="mt-8 rounded-2xl bg-white p-6">
        <h2 className="text-xl font-black">Announcement library</h2>
        {announcements.isLoading && <LoadingState label="Loading announcements..." />}
        {announcements.isError && (
          <ErrorState
            message="Announcements could not be loaded."
            onRetry={() => void announcements.refetch()}
          />
        )}
        {announcements.data?.length === 0 && (
          <p className="mt-4 text-sm text-ink/60">No announcements yet. Create a draft above.</p>
        )}
        <ul className="mt-4 divide-y divide-ink/10">
          {announcements.data?.map((item) => (
            <li className="flex flex-wrap items-center justify-between gap-4 py-4" key={item.id}>
              <div className="min-w-0">
                <h3 className="font-bold">{item.title}</h3>
                <p className="mt-1 whitespace-pre-wrap text-sm text-ink/70">{item.body}</p>
                <p className="mt-2 text-xs capitalize text-ink/55">
                  {item.audience} · {item.published_at ? "Published" : "Draft"}
                </p>
              </div>
              <div className="flex gap-2">
                <button
                  className="rounded-full border border-ink/20 px-4 py-2 text-sm font-bold"
                  onClick={() => {
                    setEditingId(item.id);
                    setAnnouncement({
                      title: item.title,
                      body: item.body,
                      audience: item.audience,
                      expires_at: item.expires_at,
                    });
                  }}
                  type="button"
                >
                  Edit
                </button>
                <button
                  className="rounded-full border border-ink/20 px-4 py-2 text-sm font-bold disabled:opacity-50"
                  disabled={publishAnnouncement.isPending}
                  onClick={() =>
                    publishAnnouncement.mutate({
                      id: item.id,
                      published: item.published_at === null,
                    })
                  }
                  type="button"
                >
                  {item.published_at ? "Unpublish" : "Publish"}
                </button>
              </div>
            </li>
          ))}
        </ul>
        {publishAnnouncement.isError && (
          <p className="mt-3 text-sm text-red-800" role="alert">
            {publishAnnouncement.error.message}
          </p>
        )}
      </section>
    </PageContainer>
  );
}