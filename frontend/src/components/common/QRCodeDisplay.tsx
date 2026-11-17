import { useState } from "react";
import { QRCodeGenerator } from "./QRCodeGenerator";

export function QRCodeDisplay({ serviceName, url }: { serviceName: string; url: string }) {
  const [copyMessage, setCopyMessage] = useState("");
  const filename =
    `${serviceName.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "service"}-qr-code.png`;

  const copyJoinLink = async () => {
    if (!navigator.clipboard?.writeText) {
      setCopyMessage("Copy is unavailable in this browser. Use the join link below.");
      return;
    }
    try {
      await navigator.clipboard.writeText(url);
      setCopyMessage("Join link copied.");
    } catch {
      setCopyMessage("Unable to copy the join link. You can select it below.");
    }
  };

  return (
    <div className="rounded-2xl border border-ink/10 bg-white p-5 text-center">
      <h3 className="font-black">{serviceName}</h3>
      <div className="mt-4 flex justify-center">
        <QRCodeGenerator
          value={url}
          alt={`${serviceName} QR code`}
          downloadName={filename}
        />
      </div>
      <button
        className="mt-4 rounded-full border border-ink/20 px-4 py-2 text-sm font-bold"
        onClick={() => void copyJoinLink()}
        type="button"
      >
        Copy join link
      </button>
      {copyMessage && (
        <p className="mt-2 text-sm text-ink/70" role="status">
          {copyMessage}
        </p>
      )}
      <a
        className="mt-3 block break-all text-xs text-emerald-800 underline"
        href={url}
      >
        {url}
      </a>
    </div>
  );
}
