import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { WaitTimeCard } from "../components/customer/WaitTimeCard";

describe("WaitTimeCard", () => {
  it("shows the statistical estimate, range, update time, and explanation", () => {
    render(
      <WaitTimeCard
        estimatedWaitMinutes={20}
        refreshedAt={Date.now()}
        prediction={{
          estimated_minutes: 18,
          lower_bound_minutes: 12,
          upper_bound_minutes: 25,
          factors: {
            explanation: "Based on 8 people ahead and 2 active counters.",
          },
        }}
      />,
    );

    expect(screen.getByText("Predictive/statistical estimation")).toBeTruthy();
    expect(screen.getByText("Estimated wait")).toBeTruthy();
    expect(screen.getByText("18 min")).toBeTruthy();
    expect(screen.getByText("Range: 12-25 min")).toBeTruthy();
    expect(
      screen.getByText("Based on 8 people ahead and 2 active counters."),
    ).toBeTruthy();
    expect(screen.getByText(/Last updated/)).toBeTruthy();
    expect(screen.queryByText(/Confidence:/)).toBeNull();
  });
});
