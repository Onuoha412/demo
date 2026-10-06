import { Link } from "react-router-dom";

import type { Service } from "../../types/api";

export function ServiceCard({ service }: { service: Service }) {
  return (
    <article className="rounded-2xl border border-ink/10 bg-white p-5">
      <p className="text-xs font-bold uppercase tracking-wide text-ink/50">{service.code}</p>
      <h3 className="mt-2 text-lg font-bold text-ink">{service.name}</h3>
      <p className="mt-2 text-sm text-ink/60">
        {service.description ?? "No description available"}
      </p>
      <p className="mt-4 text-sm text-ink/60">
        Avg. service time: <strong className="text-ink">{service.average_service_minutes} min</strong>
      </p>
      <div className="mt-4 flex gap-2">
        <Link to={`/services/${service.id}`} className="rounded-full border border-ink/20 px-4 py-2 text-sm">
          Details
        </Link>
        <Link to={`/join/${service.id}`} className="rounded-full bg-ink px-4 py-2 text-sm text-white">
          Join queue
        </Link>
      </div>
    </article>
  );
}
