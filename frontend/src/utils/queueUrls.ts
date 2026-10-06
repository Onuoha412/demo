export function serviceJoinUrl(serviceId: string, branchId?: string | null, origin = window.location.origin): string {
  if (!serviceId.trim()) throw new Error("Service ID is required");
  const path = branchId ? `/join/${encodeURIComponent(branchId)}/${encodeURIComponent(serviceId)}` : `/join/${encodeURIComponent(serviceId)}`;
  return new URL(path, origin).toString();
}
