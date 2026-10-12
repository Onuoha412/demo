export function serviceJoinPath(serviceId: string, branchId?: string | null): string {
  if (!serviceId.trim()) throw new Error("Service ID is required");
  return branchId
    ? `/join/${encodeURIComponent(branchId)}/${encodeURIComponent(serviceId)}`
    : `/join/${encodeURIComponent(serviceId)}`;
}

export function serviceJoinUrl(
  serviceId: string,
  branchId?: string | null,
  origin = window.location.origin,
  basePath = import.meta.env.BASE_URL,
): string {
  const base = basePath === "/" ? "" : `/${basePath.replace(/^\/|\/$/g, "")}`;
  return new URL(`${base}${serviceJoinPath(serviceId, branchId)}`, origin).toString();
}
