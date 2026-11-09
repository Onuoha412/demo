import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ErrorState } from "../../components/common/ErrorState";
import { LoadingState } from "../../components/common/LoadingState";
import { PageContainer } from "../../components/common/PageContainer";
import {
  downloadMigrationTemplate,
  importAdminMigration,
  listAdminMigrations,
  listAdminResource,
  previewAdminMigration,
  type MigrationJob,
} from "../../services/admin";
import { useAuthStore } from "../../store/authStore";

export function MigrationCenterPage() {
  const token = useAuthStore((state) => state.token)!;
  const user = useAuthStore((state) => state.user);
  const queryClient = useQueryClient();
  const isSuperAdmin = user?.role === "super_admin";
  const [file, setFile] = useState<File | null>(null);
  const [sourceSystem, setSourceSystem] = useState("legacy-system");
  const [organizationId, setOrganizationId] = useState("");
  const [preview, setPreview] = useState<MigrationJob | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [templateError, setTemplateError] = useState("");
  const jobs = useQuery({
    queryKey: ["admin-migrations"],
    queryFn: () => listAdminMigrations(token),
  });
  const organizations = useQuery({
    queryKey: ["admin", "organizations", "migration-center"],
    queryFn: () => listAdminResource("organizations", token, 1, 100),
    enabled: isSuperAdmin,
  });
  const previewMutation = useMutation({
    mutationFn: (data: { file: File; sourceSystem: string; organizationId?: string }) =>
      previewAdminMigration(token, data.file, data.sourceSystem, data.organizationId),
    onSuccess: (job) => {
      setPreview(job);
      setConfirmed(false);
      void queryClient.invalidateQueries({ queryKey: ["admin-migrations"] });
    },
  });
  const importMutation = useMutation({
    mutationFn: (data: { job: MigrationJob; file: File }) =>
      importAdminMigration(token, data.job.id, data.file),
    onSuccess: (job) => {
      setPreview(job);
      setConfirmed(false);
      void queryClient.invalidateQueries({ queryKey: ["admin-migrations"] });
    },
  });

  const submitPreview = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file || (isSuperAdmin && !organizationId)) return;
    setPreview(null);
    previewMutation.mutate({
      file,
      sourceSystem,
      ...(isSuperAdmin ? { organizationId } : {}),
    });
  };

  const saveTemplate = async () => {
    setTemplateError("");
    try {
      const template = await downloadMigrationTemplate(token);
      const url = URL.createObjectURL(template);
      const link = document.createElement("a");
      link.href = url;
      link.download = "queueless-import-template.csv";
      document.body.append(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 0);
    } catch (error) {
      setTemplateError(
        error instanceof Error ? error.message : "The template could not be downloaded.",
      );
    }
  };

  if (jobs.isLoading) return <LoadingState />;
  if (jobs.isError || !jobs.data) {
    return (
      <ErrorState
        message="Unable to load migration history."
        onRetry={() => void jobs.refetch()}
      />
    );
  }

  const activeRows = preview?.status === "preview"
    ? preview.preview_rows
    : preview?.result_rows ?? [];
  const failedMessage = (error: unknown) =>
    error instanceof Error ? error.message : "The request could not be completed.";

  return (
    <PageContainer className="py-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm font-bold uppercase tracking-wide text-emerald-800">
            Admin tools
          </p>
          <h1 className="mt-1 text-4xl font-black">Migration Center</h1>
        </div>
        <button
          className="rounded-full border border-ink/20 bg-white px-4 py-2 text-sm font-bold"
          type="button"
          onClick={() => void saveTemplate()}
        >
          Download CSV template
        </button>
      </div>
      <p className="mt-3 max-w-3xl text-sm text-ink/70">
        Preview a UTF-8 CSV before importing customer accounts. Passwords and
        privileged roles are never imported. Imported customers must use the
        password-reset flow to set their own password.
      </p>
      {templateError && <p className="mt-3 text-sm text-red-700" role="alert">{templateError}</p>}

      <form
        className="mt-6 grid gap-4 rounded-2xl border border-ink/10 bg-white p-5 md:grid-cols-2"
        onSubmit={submitPreview}
      >
        {isSuperAdmin && (
          <label className="grid gap-1 text-sm font-semibold md:col-span-2">
            Organization
            <select
              className="rounded-lg border border-ink/20 p-2"
              value={organizationId}
              onChange={(event) => {
                setOrganizationId(event.target.value);
                setPreview(null);
                setConfirmed(false);
              }}
              required
            >
              <option value="">Select an organization</option>
              {organizations.data?.items.map((item) => (
                <option key={String(item.id)} value={String(item.id)}>
                  {String(item.name)}
                </option>
              ))}
            </select>
            {organizations.isError && (
              <span className="font-normal text-red-700">
                Organizations could not be loaded. Retry the page.
              </span>
            )}
          </label>
        )}
        <label className="grid gap-1 text-sm font-semibold">
          Source system
          <input
            className="rounded-lg border border-ink/20 p-2"
            maxLength={80}
            pattern="[A-Za-z0-9][A-Za-z0-9._-]*"
            required
            value={sourceSystem}
            onChange={(event) => {
              setSourceSystem(event.target.value);
              setPreview(null);
              setConfirmed(false);
            }}
          />
        </label>
        <label className="grid gap-1 text-sm font-semibold">
          CSV file (up to 2 MiB and 5,000 rows)
          <input
            accept=".csv,text/csv"
            className="rounded-lg border border-ink/20 p-2"
            type="file"
            onChange={(event) => {
              setFile(event.target.files?.[0] ?? null);
              setPreview(null);
              setConfirmed(false);
            }}
          />
        </label>
        <div className="md:col-span-2">
          <p className="text-sm text-ink/60">
            Required columns: external_id, full_name, email, role, branch_id.
            Only customer and staff roles are accepted. Staff need an active
            branch in this organization; leave branch_id blank for customers.
            Existing emails are not linked.
          </p>
          <button
            className="mt-4 rounded-full bg-ink px-5 py-2 font-bold text-white disabled:opacity-50"
            disabled={
              !file ||
              (isSuperAdmin && !organizationId) ||
              previewMutation.isPending ||
              importMutation.isPending
            }
            type="submit"
          >
            {previewMutation.isPending ? "Validating CSV..." : "Upload and preview"}
          </button>
        </div>
      </form>

      {previewMutation.isError && (
        <p className="mt-4 rounded-xl bg-red-50 p-3 text-sm text-red-800" role="alert">
          Preview failed: {failedMessage(previewMutation.error)}
        </p>
      )}
      {importMutation.isError && (
        <p className="mt-4 rounded-xl bg-red-50 p-3 text-sm text-red-800" role="alert">
          Import failed: {failedMessage(importMutation.error)}
        </p>
      )}

      {preview && (
        <section className="mt-8 rounded-2xl border border-ink/10 bg-white p-5">
          <h2 className="text-2xl font-black">
            {preview.status === "preview" ? "Import preview" : "Import result"}
          </h2>
          <p className="mt-1 text-sm text-ink/60">
            Source: {preview.source_system} · SHA-256: <code>{preview.file_sha256}</code>
          </p>
          <dl className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            <Summary label="Rows" value={preview.total_rows} />
            <Summary label="Valid" value={preview.valid_rows} />
            <Summary label="Skipped" value={preview.skipped_rows} />
            <Summary label="Created" value={preview.created_rows} />
            <Summary label="Rejected" value={preview.status === "preview" ? preview.invalid_rows : preview.rejected_rows} />
          </dl>
          <div className="mt-5 overflow-x-auto">
            <table className="w-full min-w-[35rem] text-left text-sm">
              <thead>
                <tr className="border-b text-ink/60">
                  <th className="p-2">Row</th>
                  <th className="p-2">External ID</th>
                  <th className="p-2">Status</th>
                  <th className="p-2">Validation details</th>
                </tr>
              </thead>
              <tbody>
                {activeRows.map((row) => (
                  <tr className="border-b border-ink/5" key={`${row.row_number}-${row.external_id}`}>
                    <td className="p-2">{row.row_number}</td>
                    <td className="p-2">{row.external_id ?? "—"}</td>
                    <td className="p-2 capitalize">{row.status}</td>
                    <td className="p-2">{row.errors.join(" ") || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {preview.status === "preview" && (
            <div className="mt-5 border-t border-ink/10 pt-4">
              <label className="flex items-start gap-2 text-sm">
                <input
                  checked={confirmed}
                  type="checkbox"
                  onChange={(event) => setConfirmed(event.target.checked)}
                />
                <span>
                  I reviewed this preview and authorize importing the valid customer
                  rows into this organization.
                </span>
              </label>
              <button
                className="mt-4 rounded-full bg-emerald-800 px-5 py-2 font-bold text-white disabled:opacity-50"
                disabled={!confirmed || !file || importMutation.isPending}
                type="button"
                onClick={() => file && importMutation.mutate({ job: preview, file })}
              >
                {importMutation.isPending ? "Importing..." : "Confirm and import"}
              </button>
            </div>
          )}
          {preview.status === "completed" && (
            <p className="mt-4 font-bold text-emerald-800" role="status">
              Import completed and recorded in migration history.
            </p>
          )}
          {preview.status === "failed" && (
            <p className="mt-4 font-bold text-red-700" role="alert">
              Import failed. Create a new preview before retrying.
            </p>
          )}
        </section>
      )}

      <section className="mt-10">
        <div className="flex items-center justify-between gap-4">
          <h2 className="text-2xl font-black">Migration history</h2>
          <button
            className="text-sm font-bold underline"
            type="button"
            onClick={() => void jobs.refetch()}
          >
            Refresh
          </button>
        </div>
        {jobs.data.items.length === 0 ? (
          <p className="mt-3 rounded-xl bg-white p-4 text-sm text-ink/60">
            No migrations have been created yet.
          </p>
        ) : (
          <ul className="mt-3 divide-y divide-ink/10 rounded-2xl bg-white">
            {jobs.data.items.map((job) => (
              <li className="flex flex-wrap items-center justify-between gap-3 p-4" key={job.id}>
                <div>
                  <p className="font-bold">{job.source_system} · {job.status}</p>
                  <p className="text-sm text-ink/60">
                    {new Date(job.created_at).toLocaleString()} · {job.total_rows} rows ·
                    {" "}{job.created_rows} created · {job.skipped_rows} skipped · {job.rejected_rows} rejected
                  </p>
                </div>
                <button
                  className="rounded-full border px-3 py-1 text-sm font-bold"
                  type="button"
                  onClick={() => {
                    setPreview(job);
                    setConfirmed(false);
                  }}
                >
                  View details
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </PageContainer>
  );
}

function Summary({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl bg-cream p-3">
      <dt className="text-xs font-semibold text-ink/60">{label}</dt>
      <dd className="mt-1 text-xl font-black">{value}</dd>
    </div>
  );
}
