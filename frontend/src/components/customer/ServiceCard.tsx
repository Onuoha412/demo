import { Link } from "react-router-dom";

import type { Service } from "../../types/api";

const accents = [
  "from-emerald-100 to-teal-50 text-emerald-900",
  "from-sky-100 to-cyan-50 text-sky-900",
  "from-amber-100 to-orange-50 text-amber-900",
  "from-violet-100 to-fuchsia-50 text-violet-900",
];

export function ServiceCard({ service }: { service: Service }) {
  const accentIndex = [...`${service.code}${service.name}`].reduce(
    (total, character) => total + character.charCodeAt(0),
    0,
  ) % accents.length;

  return (
    <article className="group overflow-hidden rounded-3xl border border-ink/10 bg-white shadow-sm transition duration-200 hover:-translate-y-1 hover:shadow-lg">
      <div className={`bg-gradient-to-br ${accents[accentIndex]} p-5`}>
        <p className="text-xs font-bold uppercase tracking-widest opacity-70">
          Service {service.code}
        </p>
        <h3 className="mt-3 text-xl font-black">{service.name}</h3>
        <p className="mt-2 min-h-10 text-sm opacity-75">
          {service.description ?? "Join the live queue for this service."}
        </p>
      </div>
      <div className="p-5">
        <p className="text-sm text-ink/60">
          Average service time{" "}
          <strong className="text-ink">{service.average_service_minutes} min</strong>
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <Link
            to={`/services/${service.id}`}
            className="rounded-full border border-ink/20 px-4 py-2 text-sm font-semibold transition hover:bg-ink/5"
          >
          Details
          </Link>
          <Link
            to={`/join/${service.id}`}
            className="rounded-full bg-ink px-4 py-2 text-sm font-semibold text-white transition hover:bg-emerald-900"
          >
            Join queue
          </Link>
        </div>
      </div>
    </article>
  );
}
