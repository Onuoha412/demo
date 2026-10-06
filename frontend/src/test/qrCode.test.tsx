import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

const { toDataURL } = vi.hoisted(() => ({
  toDataURL: vi.fn().mockResolvedValue("data:image/png;base64,qr"),
}));

vi.mock("qrcode", () => ({ default: { toDataURL } }));

import { QRCodeGenerator } from "../components/common/QRCodeGenerator";
import { QuickJoinCard } from "../components/customer/QuickJoinCard";

describe("QRCodeGenerator", () => {
  it("encodes the public service join URL", async () => {
    toDataURL.mockClear();
    const url = "https://queueless.example/join/branch-1/service-1";
    render(<QRCodeGenerator value={url} />);

    await waitFor(() => expect(screen.getByRole("img")).toHaveAttribute("src", "data:image/png;base64,qr"));
    expect(toDataURL).toHaveBeenCalledWith(url, expect.objectContaining({ errorCorrectionLevel: "M" }));
  });

  it("QuickJoinCard encodes only the public branch and service join route", async () => {
    toDataURL.mockClear();
    render(
      <MemoryRouter>
        <QuickJoinCard
          serviceId="service-1"
          branchId="branch-1"
          serviceName="Admissions"
        />
      </MemoryRouter>,
    );

    await waitFor(() => expect(toDataURL).toHaveBeenCalled());
    const [encodedUrl] = toDataURL.mock.calls[0];
    const parsed = new URL(encodedUrl);
    expect(parsed.pathname).toBe("/join/branch-1/service-1");
    expect(parsed.search).toBe("");
    expect(parsed.username).toBe("");
    expect(parsed.password).toBe("");
    expect(screen.getByRole("link", { name: "Open join link" })).toHaveAttribute(
      "href",
      "/join/branch-1/service-1",
    );
  });
});
