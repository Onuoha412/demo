import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { EmptyState } from "../../components/common/EmptyState";
import { ErrorState } from "../../components/common/ErrorState";
import { LoadingState } from "../../components/common/LoadingState";
import { PageContainer } from "../../components/common/PageContainer";
import { ServiceCard } from "../../components/customer/ServiceCard";
import { getBranches, getOrganizations, getServices } from "../../services/queue";

export function ServicesPage() {
  const [organizationId, setOrganizationId] = useState("");
  const [branchId, setBranchId] = useState("");

  const organizations = useQuery({ queryKey: ["organizations"], queryFn: getOrganizations });
  const branches = useQuery({
    queryKey: ["branches", organizationId],
    queryFn: () => getBranches(organizationId || undefined),
  });
  const services = useQuery({
    queryKey: ["services", branchId],
    queryFn: () => getServices(branchId || undefined),
  });

  const branchOptions = useMemo(
    () => branches.data ?? [],
    [branches.data],
  );

  return (
    <PageContainer className="py-10">
      <h1 className="text-4xl font-black text-ink">Available services</h1>
      <div className="mt-6 grid gap-3 sm:grid-cols-2">
        <label className="text-sm font-semibold text-ink">
          Organization
          <select
            className="mt-1 w-full rounded-lg border border-ink/20 px-3 py-2"
            value={organizationId}
            onChange={(event) => {
              setOrganizationId(event.target.value);
              setBranchId("");
            }}
          >
            <option value="">All organizations</option>
            {(organizations.data ?? []).map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm font-semibold text-ink">
          Branch
          <select
            className="mt-1 w-full rounded-lg border border-ink/20 px-3 py-2"
            value={branchId}
            onChange={(event) => setBranchId(event.target.value)}
          >
            <option value="">All branches</option>
            {branchOptions.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="mt-8">
        {services.isLoading && <LoadingState label="Loading services..." />}
        {services.error instanceof Error && (
          <ErrorState message={services.error.message} onRetry={() => services.refetch()} />
        )}
        {services.data && services.data.length === 0 && (
          <EmptyState title="No services found" message="Try another organization or branch." />
        )}
        <div className="grid gap-4 md:grid-cols-2">
          {(services.data ?? []).map((service) => (
            <ServiceCard key={service.id} service={service} />
          ))}
        </div>
      </div>
    </PageContainer>
  );
}
