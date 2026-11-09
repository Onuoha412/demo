import { describe, expect, it } from "vitest";

import { scannedQueuePath } from "../utils/scannedQueueUrl";

describe("scannedQueuePath", () => {
  const origin = "https://queueless.example";

  it("accepts same-site service and branch join links", () => {
    expect(
      scannedQueuePath(`${origin}/join/service-1`, origin, "/"),
    ).toBe("/join/service-1");
    expect(
      scannedQueuePath(`${origin}/app/join/branch-1/service-1`, origin, "/app/"),
    ).toBe("/join/branch-1/service-1");
  });

  it("accepts a same-site queue-specific join link", () => {
    const queueId = "123e4567-e89b-42d3-a456-426614174000";
    expect(
      scannedQueuePath(
        `${origin}/join/branch-1/service-1?queue_id=${queueId}`,
        origin,
        "/",
      ),
    ).toBe(`/join/branch-1/service-1?queue_id=${queueId}`);
  });

  it.each([
    "https://other.example/join/service-1",
    "javascript:alert(1)",
    `${origin}/profile`,
    `${origin}/join/branch/service/extra`,
    `${origin}/appx/join/service-1`,
    `${origin}/join/%2Fadmin`,
    `${origin}/join/service-1?redirect=https://other.example`,
    `${origin}/join/service-1?queue_id=not-a-uuid`,
    `${origin}/join/service-1?queue_id=123e4567-e89b-42d3-a456-426614174000&queue_id=123e4567-e89b-42d3-a456-426614174000`,
  ])("rejects unsupported or unsafe QR content: %s", (value) => {
    expect(scannedQueuePath(value, origin, "/app/")).toBeNull();
  });
});
