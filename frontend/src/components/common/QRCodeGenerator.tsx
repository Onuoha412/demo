import { useEffect, useState } from "react";
import QRCode from "qrcode";

export function QRCodeGenerator({ value, size = 220 }: { value: string; size?: number }) {
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
  return result?.value === value && result.src
    ? <img src={result.src} width={size} height={size} alt="QueueLess service QR code" className="rounded-xl bg-white p-2" />
    : <div className="animate-pulse rounded-xl bg-ink/10" style={{ width: size, height: size }} aria-label="Generating QR code" />;
}
