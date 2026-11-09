import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { ErrorState } from "../../components/common/ErrorState";
import { LoadingState } from "../../components/common/LoadingState";
import { PageContainer } from "../../components/common/PageContainer";
import {
  createOrganizationAnnouncement,
  getOrganizationAnnouncements,
  setOrganizationAnnouncementPublished,
  updateOrganizationAnnouncement,
  type AnnouncementInput,
} from "../../services/operations";
import { useAuthStore } from "../../store/authStore";

const emptyAnnouncement: AnnouncementInput = {
  title: "",
  body: "",
  audience: "staff",
  expires_at: null,
};

export function OrganizationAnnouncementsPage() {
  const token = useAuthStore((state) => state.token)!;
  const queryClient = useQueryClient();
  const [announcement, setAnnouncement] = useState(emptyAnnouncement);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const announcements = useQuery({
    queryKey: ["organization-announcements"],
    queryFn: () => getOrganizationAnnouncements(token),
  });
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["organization-announcements"] });
    void queryClient.invalidateQueries({ queryKey: ["announcements", "published"] });
  };
  const save = useMutation({
    mutationFn: () =>
      editingId
        ? updateOrganizationAnnouncement(editingId, announcement, token)
        : createOrganizationAnnouncement(announcement, token),
    onSuccess: () => {
      setNotice(editingId ? "Announcement updated." : "Announcement saved as a draft.");
      setEditingId(null);
      setAnnouncement(emptyAnnouncement);
      refresh();
    },
  });
  const publish = useMutation({
    mutationFn: ({ id, isPublished }: { id: string; isPublished: boolean }) =>
      setOrganizationAnnouncementPublished(id, !isPublished, token),
    onSuccess: (_result, variables) => {
      setNotice(variables.isPublished ? "Announcement unpublished." : "Announcement published.");
      refresh();
    },
  });

  return (
    <PageContainer className="py-10">
      <p className="text-sm font-bold uppercase tracking-wide text-emerald-800">
        Organization operations
      </p>
      <h1 className="mt-2 text-4xl font-black">Staff announcements</h1>
      <p className="mt-3 max-w-3xl text-ink/70">
        Create updates for staff assigned to your organization. Organization announcements
        never appear to customers or staff at another organization.
      </p>
      {notice && <p className="mt-4 text-sm font-semibold text-emerald-900" role="status">{notice}</p>}

      <form
        className="mt-8 space-y-4 rounded-2xl bg-white p-6"
        onSubmit={(event) => {
          event.preventDefault();
          setNotice("");
          save.mutate();
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
            className="mt-1 min-h-28 w-full rounded-lg border border-ink/20 px-3 py-2"
            maxLength={5000}
            onChange={(event) =>
              setAnnouncement({ ...announcement, body: event.target.value })
            }
            required
            value={announcement.body}
          />
        </label>
        <div className="flex flex-wrap gap-3">
          <button
            className="rounded-full bg-ink px-5 py-3 font-bold text-white disabled:opacity-50"
            disabled={save.isPending}
            type="submit"
          >
            {save.isPending ? "Saving..." : editingId ? "Save changes" : "Save draft"}
          </button>
          {editingId && (
            <button
              className="rounded-full border border-ink/20 px-5 py-3 font-bold"
              onClick={() => {
                setEditingId(null);
                setAnnouncement(emptyAnnouncement);
              }}
              type="button"
            >
              Cancel edit
            </button>
          )}
        </div>
        {save.isError && <p className="text-sm text-red-800" role="alert">{save.error.message}</p>}
      </form>

      <section className="mt-8 rounded-2xl bg-white p-6">
        <h2 className="text-xl font-black">Announcement library</h2>
        {announcements.isLoading && <LoadingState label="Loading organization announcements..." />}
        {announcements.isError && (
          <ErrorState
            message="Organization announcements could not be loaded."
            onRetry={() => void announcements.refetch()}
          />
        )}
        {announcements.data?.length === 0 && (
          <p className="mt-4 text-sm text-ink/60">No announcements yet. Create a staff update above.</p>
        )}
        <ul className="mt-4 divide-y divide-ink/10">
          {announcements.data?.map((item) => (
            <li className="flex flex-wrap items-center justify-between gap-4 py-4" key={item.id}>
              <div className="min-w-0">
                <h3 className="font-bold">{item.title}</h3>
                <p className="mt-1 whitespace-pre-wrap text-sm text-ink/70">{item.body}</p>
                <p className="mt-2 text-xs text-ink/55">
                  {item.published_at ? "Published" : "Draft"}
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
                      audience: "staff",
                      expires_at: item.expires_at,
                    });
                  }}
                  type="button"
                >
                  Edit
                </button>
                <button
                  className="rounded-full border border-ink/20 px-4 py-2 text-sm font-bold disabled:opacity-50"
                  disabled={publish.isPending}
                  onClick={() =>
                    publish.mutate({
                      id: item.id,
                      isPublished: Boolean(item.published_at),
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
        {publish.isError && (
          <p className="mt-3 text-sm text-red-800" role="alert">{publish.error.message}</p>
        )}
      </section>
    </PageContainer>
  );
}
