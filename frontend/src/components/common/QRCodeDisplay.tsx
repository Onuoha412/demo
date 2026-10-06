import { QRCodeGenerator } from "./QRCodeGenerator";

export function QRCodeDisplay({ serviceName, url }: { serviceName: string; url: string }) {
  return <div className="rounded-2xl border border-ink/10 bg-white p-5 text-center"><h3 className="font-black">{serviceName}</h3><div className="mt-4 flex justify-center"><QRCodeGenerator value={url} /></div><p className="mt-3 break-all text-xs text-ink/50">{url}</p></div>;
}
