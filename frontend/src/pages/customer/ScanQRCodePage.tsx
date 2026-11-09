import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import QrScanner from "qr-scanner";

import { PageContainer } from "../../components/common/PageContainer";
import { scannedQueuePath } from "../../utils/scannedQueueUrl";

export function ScanQRCodePage() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const scannerRef = useRef<QrScanner | null>(null);
  const navigate = useNavigate();
  const [cameraState, setCameraState] = useState<
    "idle" | "starting" | "scanning" | "error"
  >("idle");
  const [message, setMessage] = useState("");
  const [fileBusy, setFileBusy] = useState(false);

  useEffect(
    () => () => {
      scannerRef.current?.destroy();
      scannerRef.current = null;
    },
    [],
  );

  const acceptScan = (value: string) => {
    const path = scannedQueuePath(value, window.location.origin, import.meta.env.BASE_URL);
    if (!path) {
      setMessage("This QR code is not a valid QueueLess join link for this site.");
      return false;
    }
    scannerRef.current?.stop();
    navigate(path);
    return true;
  };

  const startCamera = async () => {
    const video = videoRef.current;
    if (!video || scannerRef.current) return;
    setMessage("");
    setCameraState("starting");
    const scanner = new QrScanner(
      video,
      (result) => {
        if (acceptScan(result.data)) setCameraState("idle");
      },
      {
        preferredCamera: "environment",
        highlightScanRegion: true,
        returnDetailedScanResult: true,
      },
    );
    scannerRef.current = scanner;
    try {
      await scanner.start();
      setCameraState("scanning");
    } catch (error) {
      scanner.destroy();
      scannerRef.current = null;
      setCameraState("error");
      setMessage(
        error instanceof Error && error.name === "NotAllowedError"
          ? "Camera access was blocked. Allow camera access in your browser, or choose a QR image instead."
          : "Unable to start the camera. Use a secure connection and allow camera access, or choose a QR image instead.",
      );
    }
  };

  const scanImage = async (file: File | undefined) => {
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      setMessage("Choose an image file containing a QueueLess QR code.");
      return;
    }
    setFileBusy(true);
    setMessage("");
    try {
      const result = await QrScanner.scanImage(file, {
        returnDetailedScanResult: true,
      });
      acceptScan(result.data);
    } catch {
      setMessage("No readable QR code was found in that image. Try another image.");
    } finally {
      setFileBusy(false);
    }
  };

  return (
    <PageContainer className="max-w-2xl py-10">
      <h1 className="text-3xl font-black text-ink">Scan a QueueLess QR code</h1>
      <p className="mt-2 text-ink/70">
        Scan a service join code with your camera, or select an image of the code.
        You will review the service before joining.
      </p>

      <div className="mt-6 overflow-hidden rounded-2xl border border-ink/10 bg-white p-4">
        <video
          ref={videoRef}
          className="aspect-square w-full rounded-xl bg-ink object-cover"
          muted
          playsInline
          aria-label="QR code camera preview"
        />
        <div className="mt-4 flex flex-wrap gap-3">
          {cameraState === "scanning" ? (
            <button
              className="rounded-full border border-ink/20 px-5 py-3 font-bold"
              onClick={() => {
                scannerRef.current?.stop();
                scannerRef.current?.destroy();
                scannerRef.current = null;
                setCameraState("idle");
              }}
              type="button"
            >
              Stop camera
            </button>
          ) : (
            <button
              className="rounded-full bg-ink px-5 py-3 font-bold text-white disabled:opacity-60"
              disabled={cameraState === "starting"}
              onClick={() => void startCamera()}
              type="button"
            >
              {cameraState === "starting" ? "Starting camera..." : "Start camera"}
            </button>
          )}
          <label className="cursor-pointer rounded-full border border-ink/20 px-5 py-3 font-bold">
            {fileBusy ? "Reading image..." : "Choose QR image"}
            <input
              aria-label="Choose QR image"
              accept="image/*"
              className="sr-only"
              disabled={fileBusy}
              onChange={(event) => {
                void scanImage(event.target.files?.[0]);
                event.currentTarget.value = "";
              }}
              type="file"
            />
          </label>
        </div>
        {message && (
          <p className="mt-4 rounded-xl bg-amber-50 p-3 text-sm text-amber-950" role="alert">
            {message}
          </p>
        )}
      </div>

      <Link className="mt-5 inline-block font-semibold text-emerald-800 underline" to="/services">
        Browse services instead
      </Link>
    </PageContainer>
  );
}
