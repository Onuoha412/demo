export function serviceJoinPath(
  serviceId: string,
  branchId?: string | null,
  queueId?: string | null,
): string {
  if (!serviceId.trim()) throw new Error("Service ID is required");
  const path = branchId
    ? `/join/${encodeURIComponent(branchId)}/${encodeURIComponent(serviceId)}`
    : `/join/${encodeURIComponent(serviceId)}`;
  return queueId?.trim()
    ? `${path}?queue_id=${encodeURIComponent(queueId)}`
    : path;
}

export function serviceJoinUrl(
  serviceId: string,
  branchId?: string | null,
  origin = window.location.origin,
  basePath = import.meta.env.BASE_URL,
  queueId?: string | null,
): string {
  const base = basePath === "/" ? "" : `/${basePath.replace(/^\/|\/$/g, "")}`;
  return new URL(`${base}${serviceJoinPath(serviceId, branchId, queueId)}`, origin).toString();
}
