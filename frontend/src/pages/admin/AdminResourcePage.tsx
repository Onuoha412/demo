import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { ErrorState } from "../../components/common/ErrorState";
import { LoadingState } from "../../components/common/LoadingState";
import { PageContainer } from "../../components/common/PageContainer";
import { Button } from "../../components/common/Button";
import {
  createAdminResource,
  listAdminResource,
  setAdminQueueStatus,
  setAdminResourceActive,
  updateAdminResource,
  type AdminResource,
} from "../../services/admin";
import { useAuthStore } from "../../store/authStore";

const labels: Record<AdminResource, string> = {
  organizations: "Organizations",
  branches: "Branches",
  services: "Services",
  counters: "Counters",
  queues: "Queues",
  users: "Users",
};

const fields: Record<AdminResource, string[]> = {
  organizations: ["name", "slug", "description"],
  branches: ["organization_id", "name", "address", "timezone"],
  services: [
    "branch_id",
    "name",
    "code",
    "description",
    "average_service_minutes",
  ],
  counters: ["branch_id", "name", "number", "status"],
  queues: ["service_id", "name", "prefix"],
  users: [
    "full_name",
    "email",
    "password",
    "role",
    "organization_id",
    "branch_id",
  ],
};

const optionalFields = new Set([
  "description",
  "address",
  "timezone",
  "organization_id",
  "branch_id",
  "password",
]);

function isAdminResource(value: string | undefined): value is AdminResource {
  return value !== undefined && Object.hasOwn(labels, value);
}

export function AdminResourcePage() {
  const { resource: routeResource } = useParams();
  if (!isAdminResource(routeResource)) {
    return <ErrorState message="Unknown administration section." />;
  }
  return <AdminResourceContent resource={routeResource} />;
}

function AdminResourceContent({ resource }: { resource: AdminResource }) {
  const token = useAuthStore((state) => state.token)!;
  const client = useQueryClient();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [role, setRole] = useState("");
  const [form, setForm] = useState<Record<string, string>>({});
  const [editing, setEditing] = useState<string | null>(null);

  const query = useQuery({
    queryKey: ["admin", resource, page, search, role],
    queryFn: () => listAdminResource(resource, token, page, 20, search, role),
  });
  const save = useMutation({
    mutationFn: () => {
      const payload: Record<string, unknown> = {};
      for (const [key, value] of Object.entries(form)) {
        if (value === "" && optionalFields.has(key)) {
          if (key === "description" || key === "address") payload[key] = null;
          continue;
        }
        payload[key] =
          key === "number" || key === "average_service_minutes"
            ? Number(value)
            : value;
      }
      return editing
        ? updateAdminResource(resource, editing, payload, token)
        : createAdminResource(resource, payload, token);
    },
    onSuccess: () => {
      setForm({});
      setEditing(null);
      void client.invalidateQueries({ queryKey: ["admin", resource] });
    },
  });
  const toggle = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      setAdminResourceActive(resource, id, !active, token),
    onSuccess: () =>
      void client.invalidateQueries({ queryKey: ["admin", resource] }),
  });
  const status = useMutation({
    mutationFn: ({
      id,
      value,
    }: {
      id: string;
      value: "open" | "paused" | "closed";
    }) => setAdminQueueStatus(id, value, token),
    onSuccess: () =>
      void client.invalidateQueries({ queryKey: ["admin", resource] }),
  });

  if (query.isLoading) return <LoadingState />;
  if (query.isError || !query.data) {
    return (
      <ErrorState
        message={`Unable to load ${labels[resource].toLowerCase()}.`}
        onRetry={() => void query.refetch()}
      />
    );
  }

  const edit = (row: Record<string, unknown>) => {
    const id = String(row.id);
    setEditing(id);
    setForm(
      Object.fromEntries(
        fields[resource].map((field) => [
          field,
          field === "password" ? "" : String(row[field] ?? ""),
        ]),
      ),
    );
  };

  return (
    <PageContainer className="py-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <h1 className="text-4xl font-black">{labels[resource]}</h1>
        <div className="flex flex-wrap gap-2">
          <input
            aria-label="Search"
            className="rounded-lg border p-2"
            placeholder="Search"
            value={search}
            onChange={(event) => {
              setPage(1);
              setSearch(event.target.value);
            }}
          />
          {resource === "users" && (
            <select
              aria-label="Filter by role"
              className="rounded-lg border p-2"
              value={role}
              onChange={(event) => {
                setPage(1);
                setRole(event.target.value);
              }}
            >
              <option value="">All roles</option>
              <option value="customer">Customer</option>
              <option value="staff">Staff</option>
              <option value="admin">Admin</option>
            </select>
          )}
        </div>
      </div>

      {fields[resource].length > 0 && (
        <form
          className="mt-6 grid gap-3 rounded-2xl bg-white p-5 sm:grid-cols-3"
          onSubmit={(event) => {
            event.preventDefault();
            save.mutate();
          }}
        >
          {fields[resource].map((field) => (
            <label className="grid gap-1 text-sm" key={field}>
              <span className="capitalize">{field.replaceAll("_", " ")}</span>
              {field === "role" || field === "status" ? (
                <select
                  className="rounded-lg border p-2"
                  required
                  value={form[field] ?? ""}
                  onChange={(event) =>
                    setForm({ ...form, [field]: event.target.value })
                  }
                >
                  <option value="" disabled>
                    Select {field}
                  </option>
                  {(field === "role"
                    ? ["customer", "staff", "admin"]
                    : ["offline", "available", "busy"]
                  ).map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  className="rounded-lg border p-2"
                  min={
                    field === "number" || field === "average_service_minutes"
                      ? 1
                      : undefined
                  }
                  required={
                    editing
                      ? !optionalFields.has(field) && field !== "password"
                      : resource === "users"
                        ? field !== "organization_id" &&
                        (field !== "branch_id" || form.role === "staff")
                        : field !== "description" &&
                          field !== "address" &&
                          field !== "timezone"
                  }
                  type={
                    field === "password"
                      ? "password"
                      : field === "email"
                        ? "email"
                        : field === "number" ||
                            field === "average_service_minutes"
                          ? "number"
                          : "text"
                  }
                  value={form[field] ?? ""}
                  onChange={(event) =>
                    setForm({ ...form, [field]: event.target.value })
                  }
                />
              )}
            </label>
          ))}
          <div className="flex items-end gap-2">
            <Button type="submit" disabled={save.isPending}>
              {save.isPending
                ? "Saving..."
                : editing
                  ? "Save changes"
                  : "Create"}
            </Button>
            {editing && (
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  setEditing(null);
                  setForm({});
                }}
              >
                Cancel
              </Button>
            )}
          </div>
        </form>
      )}

      {(save.isError || toggle.isError || status.isError) && (
        <div className="mt-4" role="alert">
          <ErrorState message="The change could not be saved. Check the entered values and try again." />
        </div>
      )}

      <div className="mt-6 overflow-x-auto rounded-2xl bg-white">
        <table className="w-full text-left text-sm">
          <thead className="bg-ink/5">
            <tr>
              <th className="p-4">Name / ID</th>
              <th className="p-4">Status</th>
              <th className="p-4">Actions</th>
            </tr>
          </thead>
          <tbody>
            {query.data.items.map((item) => {
              const row = item as Record<string, unknown>;
              const id = String(row.id);
              const active = row.is_active as boolean | undefined;
              return (
                <tr className="border-t" key={id}>
                  <td className="p-4 font-semibold">
                    {String(row.name ?? row.full_name ?? id)}
                  </td>
                  <td className="p-4 capitalize">
                    {String(
                      row.status ??
                        (active === undefined
                          ? "—"
                          : active
                            ? "active"
                            : "inactive"),
                    )}
                  </td>
                  <td className="flex flex-wrap gap-2 p-4">
                    {fields[resource].length > 0 && (
                      <Button
                        variant="secondary"
                        onClick={() => edit(row)}
                      >
                        Edit
                      </Button>
                    )}
                    {active !== undefined && (
                      <Button
                        variant="secondary"
                        disabled={toggle.isPending}
                        onClick={() => toggle.mutate({ id, active })}
                      >
                        {active ? "Deactivate" : "Activate"}
                      </Button>
                    )}
                    {resource === "queues" && (
                      <>
                        <Button as={Link} to={`/admin/queues/${id}/entries`} variant="secondary">
                          View requests
                        </Button>
                        <Button
                          variant="secondary"
                          disabled={
                            status.isPending ||
                            row.status === "open" ||
                            row.status === "closed"
                          }
                          onClick={() => status.mutate({ id, value: "open" })}
                        >
                          Open
                        </Button>
                        <Button
                          variant="secondary"
                          disabled={
                            status.isPending ||
                            row.status === "paused" ||
                            row.status === "closed"
                          }
                          onClick={() =>
                            status.mutate({ id, value: "paused" })
                          }
                        >
                          Pause
                        </Button>
                        <Button
                          variant="secondary"
                          disabled={
                            status.isPending || row.status === "closed"
                          }
                          onClick={() =>
                            status.mutate({ id, value: "closed" })
                          }
                        >
                          Close
                        </Button>
                      </>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="mt-4 flex gap-3">
        <Button
          variant="secondary"
          disabled={page <= 1}
          onClick={() => setPage(page - 1)}
        >
          Previous
        </Button>
        <span className="py-3 text-sm">Page {page}</span>
        <Button
          variant="secondary"
          disabled={query.data.items.length < 20}
          onClick={() => setPage(page + 1)}
        >
          Next
        </Button>
      </div>
    </PageContainer>
  );
}
