import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const scannerMock = vi.hoisted(() => ({
  onDecode: undefined as
    | ((result: { data: string; cornerPoints: [] }) => void)
    | undefined,
  start: vi.fn<() => Promise<void>>(),
  stop: vi.fn(),
  destroy: vi.fn(),
  scanImage: vi.fn(),
}));

vi.mock("qr-scanner", () => ({
  default: class QrScannerMock {
    static scanImage = scannerMock.scanImage;

    constructor(
      _video: HTMLVideoElement,
      onDecode: typeof scannerMock.onDecode,
    ) {
      scannerMock.onDecode = onDecode;
    }

    start = scannerMock.start;
    stop = scannerMock.stop;
    destroy = scannerMock.destroy;
  },
}));

import { ScanQRCodePage } from "../pages/customer/ScanQRCodePage";

function renderScanner() {
  return render(
    <MemoryRouter initialEntries={["/scan"]}>
      <Routes>
        <Route path="/scan" element={<ScanQRCodePage />} />
        <Route path="/join/:serviceId" element={<p>Service join page</p>} />
        <Route path="/join/:branchId/:serviceId" element={<p>Branch service join page</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ScanQRCodePage", () => {
  beforeEach(() => {
    scannerMock.onDecode = undefined;
    scannerMock.start.mockReset().mockResolvedValue();
    scannerMock.stop.mockReset();
    scannerMock.destroy.mockReset();
    scannerMock.scanImage.mockReset();
  });

  it("opens the decoded QueueLess service join route from the camera", async () => {
    const user = userEvent.setup();
    renderScanner();

    await user.click(screen.getByRole("button", { name: "Start camera" }));
    expect(await screen.findByRole("button", { name: "Stop camera" })).toBeVisible();
    scannerMock.onDecode?.({
      data: `${window.location.origin}/join/service-1`,
      cornerPoints: [],
    });

    expect(await screen.findByText("Service join page")).toBeVisible();
    expect(scannerMock.stop).toHaveBeenCalled();
  });

  it("opens a queue-specific branch join route from the camera", async () => {
    const user = userEvent.setup();
    renderScanner();

    await user.click(screen.getByRole("button", { name: "Start camera" }));
    scannerMock.onDecode?.({
      data: `${window.location.origin}/join/branch-1/service-1?queue_id=123e4567-e89b-42d3-a456-426614174000`,
      cornerPoints: [],
    });

    expect(await screen.findByText("Branch service join page")).toBeVisible();
    expect(scannerMock.stop).toHaveBeenCalled();
  });

  it("can scan an uploaded QR image", async () => {
    scannerMock.scanImage.mockResolvedValue({
      data: `${window.location.origin}/join/service-2`,
      cornerPoints: [],
    });
    renderScanner();

    fireEvent.change(screen.getByLabelText("Choose QR image"), {
      target: { files: [new File(["qr"], "service.png", { type: "image/png" })] },
    });

    expect(await screen.findByText("Service join page")).toBeVisible();
    expect(scannerMock.scanImage).toHaveBeenCalledWith(
      expect.any(File),
      expect.objectContaining({ returnDetailedScanResult: true }),
    );
  });

  it("rejects QR content from another site", async () => {
    scannerMock.scanImage.mockResolvedValue({
      data: "https://attacker.example/join/service-3",
      cornerPoints: [],
    });
    renderScanner();

    fireEvent.change(screen.getByLabelText("Choose QR image"), {
      target: { files: [new File(["qr"], "external.png", { type: "image/png" })] },
    });

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "not a valid QueueLess join link",
    );
    expect(screen.queryByText("Service join page")).not.toBeInTheDocument();
  });

  it("shows actionable guidance when camera permission is denied", async () => {
    const permissionError = new Error("Permission denied");
    permissionError.name = "NotAllowedError";
    scannerMock.start.mockRejectedValue(permissionError);
    const user = userEvent.setup();
    renderScanner();

    await user.click(screen.getByRole("button", { name: "Start camera" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Camera access was blocked",
    );
    expect(scannerMock.destroy).toHaveBeenCalled();
  });
});
