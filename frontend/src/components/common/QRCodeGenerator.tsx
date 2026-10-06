import { useEffect, useState } from "react";
import QRCode from "qrcode";

export function QRCodeGenerator({ value, size = 220 }: { value: string; size?: number }) {
  const [src, setSrc] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    QRCode.toDataURL(value, { width: size, margin: 2, errorCorrectionLevel: "M" })
      .then((url) => { if (active) { setSrc(url); setError(null); } })
      .catch(() => { if (active) setError("Unable to generate this QR code."); });
    return () => { active = false; };
  }, [value, size]);
  if (error) return <p className="text-sm text-red-600">{error}</p>;
  return src ? <img src={src} width={size} height={size} alt="QueueLess service QR code" className="rounded-xl bg-white p-2" /> : <div className="h-56 w-56 animate-pulse rounded-xl bg-ink/10" aria-label="Generating QR code" />;
}
