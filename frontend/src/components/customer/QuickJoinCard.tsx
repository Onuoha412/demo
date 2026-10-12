import { Link } from "react-router-dom";
import { QRCodeDisplay } from "../common/QRCodeDisplay";
import { serviceJoinPath, serviceJoinUrl } from "../../utils/queueUrls";

export function QuickJoinCard({ serviceId, branchId, serviceName }: { serviceId: string; branchId?: string; serviceName: string }) {
  const url = serviceJoinUrl(serviceId, branchId);
  return <div className="mt-8 grid gap-4 sm:grid-cols-2"><div className="rounded-2xl bg-emerald-50 p-5"><h3 className="font-black">Quick join</h3><p className="mt-2 text-sm text-ink/70">Scan this code to open the service and join securely. It contains no private data.</p><Link to={serviceJoinPath(serviceId, branchId)} className="mt-4 inline-block rounded-full bg-ink px-4 py-2 text-sm font-bold text-white">Open join link</Link></div><QRCodeDisplay serviceName={serviceName} url={url} /></div>;
}
