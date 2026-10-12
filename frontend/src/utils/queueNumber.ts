export function formatQueueNumber(prefix: string, number: number): string {
  return `${prefix}${String(number).padStart(3, "0")}`;
}
