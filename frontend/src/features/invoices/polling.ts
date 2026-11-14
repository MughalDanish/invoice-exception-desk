export function processingPoll(
  status?: string,
  updatedAt?: string,
  now = Date.now(),
) {
  if (status !== "EXTRACTING" || !updatedAt) return false;
  const updated = Date.parse(updatedAt);
  return Number.isFinite(updated) && updated <= now && now - updated < 240000;
}
