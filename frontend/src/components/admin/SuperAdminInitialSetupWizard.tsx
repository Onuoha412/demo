import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { ApiError } from "../../services/api";
import {
  createSuperAdminInitialSetup,
  type SuperAdminInitialSetupInput,
} from "../../services/superAdmin";

function createSlug(value: string) {
  return value
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 160);
}

export function SuperAdminInitialSetupWizard({
  token,
  onComplete,
}: {
  token: string;
  onComplete: () => void;
}) {
  const queryClient = useQueryClient();
  const [organizationName, setOrganizationName] = useState("");
  const [organizationSlug, setOrganizationSlug] = useState("");
  const [slugEdited, setSlugEdited] = useState(false);
  const [branchName, setBranchName] = useState("");
  const [branchAddress, setBranchAddress] = useState("");
  const [timezone, setTimezone] = useState("UTC");
  const [serviceName, setServiceName] = useState("");
  const [serviceCode, setServiceCode] = useState("");
  const [averageServiceMinutes, setAverageServiceMinutes] = useState("10");
  const [queueName, setQueueName] = useState("");
  const [queuePrefix, setQueuePrefix] = useState("");
  const [completed, setCompleted] = useState(false);

  const setup = useMutation({
    mutationFn: (input: SuperAdminInitialSetupInput) =>
      createSuperAdminInitialSetup(input, token),
    onSuccess: async () => {
      setCompleted(true);
      onComplete();
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["super-admin-dashboard"] }),
        queryClient.invalidateQueries({ queryKey: ["admin", "organizations"] }),
        queryClient.invalidateQueries({ queryKey: ["admin", "branches"] }),
        queryClient.invalidateQueries({ queryKey: ["admin", "services"] }),
        queryClient.invalidateQueries({ queryKey: ["admin", "queues"] }),
      ]);
    },
  });

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const input: SuperAdminInitialSetupInput = {
      organization_name: organizationName.trim(),
      organization_slug: organizationSlug.trim(),
      branch_name: branchName.trim(),
      branch_address: branchAddress.trim() || null,
      timezone: timezone.trim(),
      service_name: serviceName.trim(),
      service_code: serviceCode.trim().toUpperCase(),
      average_service_minutes: Number(averageServiceMinutes),
      queue_name: queueName.trim(),
      queue_prefix: queuePrefix.trim().toUpperCase(),
    };
    setup.mutate(input);
  };

  if (completed) {
    return (
      <section
        aria-labelledby="initial-setup-heading"
        className="mt-8 rounded-2xl border border-emerald-200 bg-emerald-50 p-6"
      >
        <h2 id="initial-setup-heading" className="text-xl font-black">
          Your QueueLess workspace is ready
        </h2>
        <p className="mt-2 text-sm text-emerald-950" role="status">
          The organization, branch, service, and open queue were created.
        </p>
        <div className="mt-4 flex flex-wrap gap-4 text-sm font-bold text-emerald-900">
          <Link to="/super-admin/organizations" className="underline">
            Manage organizations
          </Link>
          <Link to="/super-admin/services" className="underline">
            Manage services
          </Link>
        </div>
      </section>
    );
  }

  return (
    <section
      aria-labelledby="initial-setup-heading"
      className="mt-8 rounded-2xl border border-emerald-200 bg-white p-6"
    >
      <p className="text-sm font-bold uppercase tracking-wide text-emerald-800">
        First-time setup
      </p>
      <h2 id="initial-setup-heading" className="mt-1 text-2xl font-black">
        Set up your organization
      </h2>
      <p className="mt-2 max-w-3xl text-sm text-ink/70">
        Enter your real organization details. We’ll create the organization, its
        first branch, one service, and that service’s open queue together. No
        sample records are added.
      </p>

      <form className="mt-6 space-y-6" onSubmit={submit}>
        <fieldset className="grid gap-4 sm:grid-cols-2">
          <legend className="mb-3 font-bold">Organization</legend>
          <label className="text-sm font-semibold">
            Organization name
            <input
              aria-label="Organization name"
              autoComplete="organization"
              className="mt-1 w-full rounded-xl border border-ink/15 p-3"
              maxLength={160}
              onChange={(event) => {
                const value = event.target.value;
                setOrganizationName(value);
                if (!slugEdited) setOrganizationSlug(createSlug(value));
              }}
              required
              value={organizationName}
            />
          </label>
          <label className="text-sm font-semibold">
            Organization URL slug
            <input
              aria-label="Organization URL slug"
              className="mt-1 w-full rounded-xl border border-ink/15 p-3"
              maxLength={160}
              onChange={(event) => {
                setSlugEdited(true);
                setOrganizationSlug(createSlug(event.target.value));
              }}
              pattern="[a-z0-9]+(-[a-z0-9]+)*"
              required
              value={organizationSlug}
            />
          </label>
        </fieldset>

        <fieldset className="grid gap-4 sm:grid-cols-2">
          <legend className="mb-3 font-bold">First branch</legend>
          <label className="text-sm font-semibold">
            Branch name
            <input
              aria-label="Branch name"
              className="mt-1 w-full rounded-xl border border-ink/15 p-3"
              maxLength={160}
              onChange={(event) => setBranchName(event.target.value)}
              required
              value={branchName}
            />
          </label>
          <label className="text-sm font-semibold">
            Time zone
            <input
              aria-label="Time zone"
              className="mt-1 w-full rounded-xl border border-ink/15 p-3"
              maxLength={64}
              onChange={(event) => setTimezone(event.target.value)}
              required
              value={timezone}
            />
          </label>
          <label className="text-sm font-semibold sm:col-span-2">
            Address (optional)
            <input
              aria-label="Branch address"
              autoComplete="street-address"
              className="mt-1 w-full rounded-xl border border-ink/15 p-3"
              maxLength={255}
              onChange={(event) => setBranchAddress(event.target.value)}
              value={branchAddress}
            />
          </label>
        </fieldset>

        <fieldset className="grid gap-4 sm:grid-cols-2">
          <legend className="mb-3 font-bold">First service and queue</legend>
          <label className="text-sm font-semibold">
            Service name
            <input
              aria-label="Service name"
              className="mt-1 w-full rounded-xl border border-ink/15 p-3"
              maxLength={160}
              onChange={(event) => setServiceName(event.target.value)}
              required
              value={serviceName}
            />
          </label>
          <label className="text-sm font-semibold">
            Service code
            <input
              aria-label="Service code"
              className="mt-1 w-full rounded-xl border border-ink/15 p-3 uppercase"
              maxLength={32}
              onChange={(event) => setServiceCode(event.target.value)}
              required
              value={serviceCode}
            />
          </label>
          <label className="text-sm font-semibold">
            Average service time (minutes)
            <input
              aria-label="Average service time in minutes"
              className="mt-1 w-full rounded-xl border border-ink/15 p-3"
              min={1}
              onChange={(event) => setAverageServiceMinutes(event.target.value)}
              required
              type="number"
              value={averageServiceMinutes}
            />
          </label>
          <label className="text-sm font-semibold">
            Queue name
            <input
              aria-label="Queue name"
              className="mt-1 w-full rounded-xl border border-ink/15 p-3"
              maxLength={160}
              onChange={(event) => setQueueName(event.target.value)}
              required
              value={queueName}
            />
          </label>
          <label className="text-sm font-semibold">
            Queue ticket prefix
            <input
              aria-label="Queue ticket prefix"
              className="mt-1 w-full rounded-xl border border-ink/15 p-3 uppercase"
              maxLength={10}
              onChange={(event) => setQueuePrefix(event.target.value)}
              required
              value={queuePrefix}
            />
          </label>
        </fieldset>

        {setup.error && (
          <p className="text-sm text-red-700" role="alert">
            {setup.error instanceof ApiError
              ? setup.error.detail
              : "The setup could not be completed. Check the details and try again."}
          </p>
        )}

        <button
          className="rounded-full bg-ink px-6 py-3 font-bold text-white disabled:opacity-60"
          disabled={setup.isPending}
          type="submit"
        >
          {setup.isPending ? "Creating your workspace..." : "Create my workspace"}
        </button>
      </form>
    </section>
  );
}
