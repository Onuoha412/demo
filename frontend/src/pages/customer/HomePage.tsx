import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Clock3, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";

import { EmptyState } from "../../components/common/EmptyState";
import { ErrorState } from "../../components/common/ErrorState";
import { LoadingState } from "../../components/common/LoadingState";
import { PageContainer } from "../../components/common/PageContainer";
import { ServiceCard } from "../../components/customer/ServiceCard";
import { getServices } from "../../services/queue";

export function HomePage() {
  const services = useQuery({
    queryKey: ["services", "home"],
    queryFn: () => getServices(),
    staleTime: 30_000,
  });

  return (
    <PageContainer className="py-10 sm:py-16">
      <section className="relative overflow-hidden rounded-[2rem] bg-ink px-6 py-12 text-white sm:px-12 sm:py-16">
        <div className="pointer-events-none absolute -right-20 -top-24 h-72 w-72 rounded-full bg-emerald-400/20 blur-3xl" />
        <div className="relative max-w-3xl">
          <p className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/10 px-3 py-1 text-sm font-semibold text-emerald-200">
            <Sparkles aria-hidden="true" size={16} />
            A better way to wait
          </p>
          <h1 className="mt-6 text-4xl font-black tracking-tight sm:text-6xl">
            Your time is yours again.
          </h1>
          <p className="mt-5 max-w-2xl text-base leading-7 text-white/75 sm:text-lg">
            Find a service, join its live queue, and follow your place in line
            from wherever you are.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              to="/services"
              className="inline-flex items-center gap-2 rounded-full bg-emerald-300 px-6 py-3 font-bold text-ink transition hover:bg-emerald-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
            >
              Explore services
              <ArrowRight aria-hidden="true" size={18} />
            </Link>
            <Link
              to="/register"
              className="rounded-full border border-white/25 px-6 py-3 font-semibold text-white transition hover:bg-white/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
            >
              Create account
            </Link>
          </div>
        </div>
        <div className="relative mt-10 grid max-w-2xl gap-3 sm:grid-cols-2">
          <div className="rounded-2xl border border-white/10 bg-white/10 p-4 backdrop-blur">
            <Clock3 aria-hidden="true" className="text-emerald-200" size={20} />
            <p className="mt-3 font-bold">Know before you go</p>
            <p className="mt-1 text-sm text-white/65">
              See your position and estimated wait update in real time.
            </p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/10 p-4 backdrop-blur">
            <ArrowRight aria-hidden="true" className="text-emerald-200" size={20} />
            <p className="mt-3 font-bold">Join from anywhere</p>
            <p className="mt-1 text-sm text-white/65">
              Choose a real service and join its open queue when you are ready.
            </p>
          </div>
        </div>
      </section>

      <section className="mt-14">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-sm font-bold uppercase tracking-widest text-emerald-800">
              Made for your day
            </p>
            <h2 className="mt-2 text-3xl font-black tracking-tight text-ink">
              Find your service
            </h2>
          </div>
          <Link
            to="/services"
            className="inline-flex items-center gap-2 font-semibold text-emerald-800 hover:text-emerald-950"
          >
            Browse all services
            <ArrowRight aria-hidden="true" size={17} />
          </Link>
        </div>

        <div className="mt-6">
          {services.isLoading && <LoadingState label="Finding available services..." />}
          {services.error instanceof Error && (
            <ErrorState
              message={services.error.message}
              onRetry={() => void services.refetch()}
            />
          )}
          {services.data && services.data.length === 0 && (
            <EmptyState
              title="No services available yet"
              message="Check back when an organization publishes its services."
            />
          )}
          {services.data && services.data.length > 0 && (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {services.data.slice(0, 3).map((service) => (
                <ServiceCard key={service.id} service={service} />
              ))}
            </div>
          )}
        </div>
      </section>
    </PageContainer>
  );
}
