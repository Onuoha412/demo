import { describe, expect, it } from "vitest";
import { serviceJoinUrl } from "../utils/queueUrls";

describe("serviceJoinUrl", () => {
  it("builds the standard service join URL", () => {
    expect(serviceJoinUrl("service-123", null, "https://queueless.example"))
      .toBe("https://queueless.example/join/service-123");
  });

  it("builds the branch-specific join URL", () => {
    expect(serviceJoinUrl("service-123", "branch-456", "https://queueless.example"))
      .toBe("https://queueless.example/join/branch-456/service-123");
  });

  it("builds a queue-specific QR URL", () => {
    expect(
      serviceJoinUrl(
        "service-123",
        "branch-456",
        "https://queueless.example",
        "/",
        "queue-789",
      ),
    ).toBe(
      "https://queueless.example/join/branch-456/service-123?queue_id=queue-789",
    );
  });

  it("keeps a deployment base path in the scannable URL", () => {
    expect(
      serviceJoinUrl("service-123", "branch-456", "https://queueless.example", "/app/"),
    ).toBe("https://queueless.example/app/join/branch-456/service-123");
  });

  it("does not build a URL without a service identifier", () => {
    expect(() => serviceJoinUrl(" ", null, "https://queueless.example")).toThrow("Service ID is required");
  });
});
