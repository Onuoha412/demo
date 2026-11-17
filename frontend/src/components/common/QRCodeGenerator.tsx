import { useEffect, useState } from "react";
import QRCode from "qrcode";

export function QRCodeGenerator({
  value,
  size = 220,
  alt = "QueueLess QR code",
  downloadName = "queueless-qr-code.png",
}: {
  value: string;
  size?: number;
  alt?: string;
  downloadName?: string;
}) {
  const [result, setResult] = useState<{
    value: string;
    src?: string;
    error?: string;
  }>();
  useEffect(() => {
    let active = true;
    QRCode.toDataURL(value, { width: size, margin: 2, errorCorrectionLevel: "M" })
      .then((url) => { if (active) setResult({ value, src: url }); })
      .catch(() => { if (active) setResult({ value, error: "Unable to generate this QR code." }); });
    return () => { active = false; };
  }, [value, size]);
  if (result?.value === value && result.error) {
    return <p className="text-sm text-red-600">{result.error}</p>;
  }
  return result?.value === value && result.src ? (
    <div className="flex flex-col items-center gap-3">
      <img
        src={result.src}
        width={size}
        height={size}
        alt={alt}
        className="rounded-xl bg-white p-2"
      />
      <a
        className="text-sm font-bold text-emerald-800 underline"
        download={downloadName}
        href={result.src}
      >
        Download QR code
      </a>
    </div>
  ) : (
    <div
      className="animate-pulse rounded-xl bg-ink/10"
      style={{ width: size, height: size }}
      aria-label="Generating QR code"
    />
  );
}
