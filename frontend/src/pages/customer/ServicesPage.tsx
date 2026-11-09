import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { EmptyState } from "../../components/common/EmptyState";
import { ErrorState } from "../../components/common/ErrorState";
import { LoadingState } from "../../components/common/LoadingState";
import { PageContainer } from "../../components/common/PageContainer";
import { ServiceCard } from "../../components/customer/ServiceCard";
import { getBranches, getOrganizations, getServices } from "../../services/queue";

export function ServicesPage() {
  const [searchParams] = useSearchParams();
  const [organizationId, setOrganizationId] = useState(
    () => searchParams.get("organization_id") ?? "",
  );
  const [branchId, setBranchId] = useState(
    () => searchParams.get("branch_id") ?? "",
  );
  const [searchTerm, setSearchTerm] = useState("");

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
  const visibleServices = useMemo(() => {
    const normalizedSearch = searchTerm.trim().toLowerCase();
    return (services.data ?? []).filter((service) =>
      [service.name, service.code, service.description ?? ""].some((value) =>
        value.toLowerCase().includes(normalizedSearch),
      ),
    );
  }, [searchTerm, services.data]);

  return (
    <PageContainer className="py-10">
      <h1 className="text-4xl font-black text-ink">Available services</h1>
      <label className="mt-6 block text-sm font-semibold text-ink">
        Search services
        <input
          className="mt-1 w-full rounded-lg border border-ink/20 px-3 py-2"
          onChange={(event) => setSearchTerm(event.target.value)}
          placeholder="Search by service name, code, or description"
          type="search"
          value={searchTerm}
        />
      </label>
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
        {services.data && visibleServices.length === 0 && (
          <EmptyState
            title={services.data.length === 0 ? "No services found" : "No matching services"}
            message={
              services.data.length === 0
                ? "Try another organization or branch."
                : "Try a different search term."
            }
          />
        )}
        <div className="grid gap-4 md:grid-cols-2">
          {visibleServices.map((service) => (
            <ServiceCard key={service.id} service={service} />
          ))}
        </div>
      </div>
    </PageContainer>
  );
}
