export function scannedQueuePath(
  value: string,
  origin: string,
  basePath: string,
): string | null {
  let scanned: URL;
  try {
    scanned = new URL(value);
  } catch {
    return null;
  }

  if (
    !["http:", "https:"].includes(scanned.protocol) ||
    scanned.origin !== origin ||
    scanned.hash
  ) {
    return null;
  }

  const searchParams = [...scanned.searchParams.entries()];
  if (
    searchParams.length > 1 ||
    (searchParams.length === 1 &&
      (searchParams[0][0] !== "queue_id" ||
        !/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
          searchParams[0][1],
        )))
  ) {
    return null;
  }

  const base = basePath === "/" ? "" : `/${basePath.replace(/^\/|\/$/g, "")}`;
  if (base && !scanned.pathname.startsWith(`${base}/`)) return null;
  const appPath = base ? scanned.pathname.slice(base.length) : scanned.pathname;
  const segments = appPath.split("/").filter(Boolean);
  if (segments[0] !== "join" || (segments.length !== 2 && segments.length !== 3)) {
    return null;
  }
  try {
    if (
      segments.slice(1).some((segment) => {
        const decoded = decodeURIComponent(segment);
        return !decoded || decoded === "." || decoded === ".." || decoded.includes("/");
      })
    ) {
      return null;
    }
  } catch {
    return null;
  }
  return `${appPath}${scanned.search}`;
}
