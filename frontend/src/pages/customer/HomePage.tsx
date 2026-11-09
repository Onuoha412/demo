import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  BellRing,
  Check,
  MapPin,
  Sparkles,
  TicketCheck,
} from "lucide-react";
import { Link } from "react-router-dom";

import { EmptyState } from "../../components/common/EmptyState";
import { ErrorState } from "../../components/common/ErrorState";
import { LoadingState } from "../../components/common/LoadingState";
import { PageContainer } from "../../components/common/PageContainer";
import { ServiceCard } from "../../components/customer/ServiceCard";
import { CustomerHomeSummary } from "../../components/customer/CustomerHomeSummary";
import { AnnouncementFeed } from "../../components/common/AnnouncementFeed";
import { MyQueueRequestsPanel } from "../../components/queue/MyQueueRequestsPanel";
import { getServices } from "../../services/queue";

const steps = [
  {
    icon: MapPin,
    number: "01",
    title: "Find your service",
    description: "Choose the service and location that work for you.",
  },
  {
    icon: TicketCheck,
    number: "02",
    title: "Take your place",
    description: "Join the queue online and keep your ticket close.",
  },
  {
    icon: BellRing,
    number: "03",
    title: "Make time yours",
    description: "Track your place and head over when it’s nearly your turn.",
  },
];

export function HomePage() {
  const services = useQuery({
    queryKey: ["services", "home"],
    queryFn: () => getServices(),
    staleTime: 30_000,
  });

  return (
    <main>
      <section className="relative isolate overflow-hidden bg-ink text-white">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 -z-10 overflow-hidden"
        >
          <div className="absolute -right-32 -top-48 h-[34rem] w-[34rem] rounded-full bg-emerald-400/15 blur-3xl" />
          <div className="absolute -bottom-80 left-[28%] h-[34rem] w-[34rem] rounded-full bg-lime-300/10 blur-3xl" />
          <div className="absolute inset-0 opacity-[0.07] [background-image:radial-gradient(#d9f99d_1px,transparent_1px)] [background-size:24px_24px]" />
        </div>

        <PageContainer className="grid min-h-[34rem] items-center gap-12 py-14 sm:py-20 lg:grid-cols-[1.1fr_0.9fr] lg:gap-16 lg:py-24">
          <div className="max-w-2xl">
            <p className="inline-flex items-center gap-2 rounded-full border border-emerald-200/20 bg-white/[0.06] px-3.5 py-1.5 text-sm font-semibold text-emerald-200">
              <Sparkles aria-hidden="true" size={16} />
              Less waiting. More living.
            </p>
            <h1 className="mt-7 text-5xl font-black leading-[1.04] tracking-[-0.045em] sm:text-6xl lg:text-7xl">
              Your time is
              <br />
              <span className="text-mint">yours again.</span>
            </h1>
            <p className="mt-6 max-w-xl text-base leading-7 text-white/70 sm:text-lg sm:leading-8">
              Join a queue from wherever you are. Know where you stand, get on
              with your day, and show up when it matters.
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Link
                to="/services"
                className="inline-flex min-h-12 items-center justify-center gap-2 rounded-full bg-mint px-6 font-bold text-ink shadow-lg shadow-black/10 transition hover:-translate-y-0.5 hover:bg-lime-200 focus-visible:outline-white"
              >
                Find a service
                <ArrowRight aria-hidden="true" size={18} />
              </Link>
              <Link
                to="/register"
                className="inline-flex min-h-12 items-center justify-center rounded-full border border-white/20 px-6 font-semibold text-white transition hover:border-white/40 hover:bg-white/[0.06] focus-visible:outline-white"
              >
                Create a free account
              </Link>
            </div>
            <div className="mt-8 flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-white/55">
              <span className="inline-flex items-center gap-2">
                <Check aria-hidden="true" className="text-emerald-300" size={16} />
                No waiting-room guesswork
              </span>
              <span className="inline-flex items-center gap-2">
                <Check aria-hidden="true" className="text-emerald-300" size={16} />
                Updates as your queue moves
              </span>
            </div>
          </div>

          <div className="relative mx-auto w-full max-w-md lg:ml-auto">
            <div
              aria-hidden="true"
              className="absolute -inset-5 rounded-[2.5rem] border border-white/[0.08] sm:-inset-7"
            />
            <section
              aria-label="Published services"
              aria-busy={services.isLoading}
              className="relative overflow-hidden rounded-[1.75rem] border border-white/10 bg-[#f8faf5] text-ink shadow-2xl shadow-black/25"
            >
              <div className="flex items-center gap-3 border-b border-ink/10 px-5 py-4 sm:px-6">
                <span className="grid h-10 w-10 place-items-center rounded-xl bg-emerald-100 text-emerald-900">
                  <MapPin aria-hidden="true" size={19} />
                </span>
                <div>
                  <p className="text-sm font-bold">Find a service</p>
                  <p className="text-xs text-ink/55">Published by service providers</p>
                </div>
              </div>
              <div className="space-y-3 p-4 sm:p-5">
                {services.isLoading && (
                  <p className="rounded-xl bg-white p-4 text-sm text-ink/60" role="status">
                    Loading available services…
                  </p>
                )}
                {services.isError && (
                  <div className="rounded-xl bg-red-50 p-4 text-sm text-red-800" role="alert">
                    <p>Services could not be loaded right now.</p>
                    <button
                      className="mt-3 rounded-full border border-red-200 bg-white px-3 py-2 text-xs font-bold text-red-800 transition hover:bg-red-100"
                      onClick={() => void services.refetch()}
                      type="button"
                    >
                      Try again
                    </button>
                  </div>
                )}
                {services.data?.length === 0 && (
                  <p className="rounded-xl bg-white p-4 text-sm text-ink/60">
                    No services have been published yet.
                  </p>
                )}
                {services.data?.slice(0, 2).map((service) => (
                  <Link
                    className="group flex items-center justify-between gap-4 rounded-xl bg-white p-4 transition hover:bg-emerald-50 focus-visible:outline-emerald-700"
                    key={service.id}
                    to={`/services/${service.id}`}
                  >
                    <span className="min-w-0">
                      <span className="block truncate font-bold text-ink">
                        {service.name}
                      </span>
                      <span className="mt-1 block text-xs text-ink/55">
                        Average service time · {service.average_service_minutes} min
                      </span>
                    </span>
                    <ArrowRight
                      aria-hidden="true"
                      className="shrink-0 text-emerald-800 transition group-hover:translate-x-1"
                      size={18}
                    />
                  </Link>
                ))}
                <Link
                  className="inline-flex min-h-10 items-center gap-2 px-2 text-sm font-bold text-emerald-800 hover:text-emerald-950"
                  to="/services"
                >
                  Browse the service directory
                  <ArrowRight aria-hidden="true" size={16} />
                </Link>
              </div>
            </section>
            <div className="absolute -bottom-5 -left-3 hidden items-center gap-3 rounded-2xl border border-white/70 bg-white px-4 py-3 shadow-xl sm:flex">
              <span className="grid h-9 w-9 place-items-center rounded-full bg-emerald-100 text-emerald-800">
                <BellRing aria-hidden="true" size={17} />
              </span>
              <span>
                <span className="block text-xs font-bold text-ink">Stay in the loop</span>
                <span className="block text-xs text-ink/55">Your place, updated live</span>
              </span>
            </div>
          </div>
        </PageContainer>
      </section>

      <CustomerHomeSummary />
      <AnnouncementFeed />

      <PageContainer className="py-16 sm:py-20">
        <section aria-labelledby="how-it-works">
          <div className="max-w-2xl">
            <p className="text-sm font-bold uppercase tracking-[0.18em] text-emerald-800">
              A better way to get there
            </p>
            <h2
              id="how-it-works"
              className="mt-3 text-3xl font-black tracking-tight text-ink sm:text-4xl"
            >
              Your day, without the waiting room.
            </h2>
          </div>
          <div className="mt-8 grid gap-4 md:grid-cols-3">
            {steps.map(({ icon: Icon, number, title, description }) => (
              <article
                key={number}
                className="rounded-3xl border border-ink/10 bg-white p-6 transition hover:-translate-y-1 hover:shadow-lg hover:shadow-ink/5 sm:p-7"
              >
                <div className="flex items-center justify-between">
                  <span className="grid h-12 w-12 place-items-center rounded-2xl bg-emerald-50 text-emerald-800">
                    <Icon aria-hidden="true" size={22} />
                  </span>
                  <span className="text-sm font-bold tracking-widest text-ink/30">{number}</span>
                </div>
                <h3 className="mt-6 text-lg font-black text-ink">{title}</h3>
                <p className="mt-2 text-sm leading-6 text-ink/60">{description}</p>
              </article>
            ))}
          </div>
        </section>

        <section aria-labelledby="services-heading" className="mt-20 sm:mt-24">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="text-sm font-bold uppercase tracking-[0.18em] text-emerald-800">
                Start with what you need
              </p>
              <h2
                id="services-heading"
                className="mt-3 text-3xl font-black tracking-tight text-ink sm:text-4xl"
              >
                Find your service.
              </h2>
            </div>
            <Link
              to="/services"
              className="inline-flex items-center gap-2 rounded-full px-1 py-2 font-semibold text-emerald-800 transition hover:text-emerald-950 focus-visible:outline-emerald-700"
            >
              Browse all services
              <ArrowRight aria-hidden="true" size={17} />
            </Link>
          </div>

          <div className="mt-7">
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

        <MyQueueRequestsPanel />
      </PageContainer>
    </main>
  );
}
