import type { ReactNode } from "react";
import { ArrowRight, BellRing, Check, Clock3, TicketCheck } from "lucide-react";
import { Link } from "react-router-dom";

const ticketDetails = [
  {
    icon: TicketCheck,
    label: "Queue number",
    detail: "Assigned when you join",
  },
  {
    icon: ArrowRight,
    label: "Your position",
    detail: "Updates as the queue moves",
  },
  {
    icon: Clock3,
    label: "Estimated wait",
    detail: "Calculated for your queue",
  },
];

export function AuthLayout({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: ReactNode;
}) {
  return (
    <main className="mx-auto grid min-h-[calc(100vh-4rem)] max-w-7xl items-stretch gap-8 px-4 py-8 lg:grid-cols-[1.08fr_0.92fr] lg:px-8">
      <section className="flex items-center justify-center">
        <div className="w-full max-w-lg rounded-[2rem] border border-slate-200/80 bg-white/90 p-6 shadow-[0_30px_80px_rgba(15,23,42,0.10)] backdrop-blur-sm sm:p-10">
          <Link
            to="/"
            className="inline-flex items-center gap-3 text-xl font-black tracking-[-0.04em] text-slate-900"
          >
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-100 text-lg text-emerald-700 shadow-inner">
              Q
            </span>
            Queue<span className="text-emerald-700">Less</span>
          </Link>

          <p className="mt-8 text-xs font-bold uppercase tracking-[0.22em] text-emerald-700">
            Queue smarter
          </p>
          <h1 className="mt-2 text-4xl font-black tracking-[-0.06em] text-slate-900">
            {title}
          </h1>
          <p className="mt-3 text-base text-slate-600">{subtitle}</p>

          <div className="mt-8">{children}</div>
        </div>
      </section>

      <aside className="queue-auth-art relative hidden min-h-[40rem] overflow-hidden rounded-[2rem] bg-[radial-gradient(circle_at_top_left,#1b3b42_0%,#0a1f2a_32%,#07161d_100%)] p-8 text-white shadow-[0_30px_80px_rgba(15,23,42,0.18)] lg:flex lg:flex-col lg:justify-between">
        <div className="absolute inset-0 opacity-40" aria-hidden="true">
          <div className="auth-orbit auth-orbit-one" />
          <div className="auth-orbit auth-orbit-two" />
        </div>

        <div className="relative z-10 flex items-center justify-between text-sm text-emerald-50/80">
          <span className="inline-flex items-center gap-2 font-semibold uppercase tracking-[0.3em]">
            <span className="inline-block h-2 w-2 rounded-full bg-emerald-300" />
            QueueLess
          </span>
          <span className="rounded-full border border-white/15 bg-white/5 px-3 py-1.5">
            Queue management
          </span>
        </div>

        <div className="relative z-10">
          <p className="text-xs font-bold uppercase tracking-[0.28em] text-emerald-200/90">
            Your time, back in your hands
          </p>
          <h2 className="mt-4 max-w-lg text-4xl font-black leading-tight tracking-[-0.06em] text-white">
            Know where you stand. Get on with your day.
          </h2>
          <p className="mt-4 max-w-md text-base leading-7 text-slate-200/80">
            Join an available service and your ticket will show the details for
            your real place in its queue.
          </p>
        </div>

        <section
          aria-label="Queue ticket information"
          className="relative z-10 mx-auto w-full max-w-md rounded-[1.6rem] border border-white/15 bg-white/[0.07] p-5 shadow-[0_20px_50px_rgba(16,185,129,0.12)] backdrop-blur-lg sm:p-6"
        >
          <div className="flex items-center gap-3 border-b border-white/10 pb-4">
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-emerald-300 text-slate-900">
              <TicketCheck aria-hidden="true" size={20} />
            </span>
            <div>
              <p className="font-bold text-white">Your queue ticket</p>
              <p className="text-xs text-slate-200/65">Created when you join a queue</p>
            </div>
          </div>
          <div className="mt-2 divide-y divide-white/10">
            {ticketDetails.map(({ icon: Icon, label, detail }) => (
              <div className="flex items-center gap-3 py-4" key={label}>
                <Icon aria-hidden="true" className="shrink-0 text-emerald-200" size={18} />
                <span className="min-w-0">
                  <span className="block text-sm font-semibold text-white">{label}</span>
                  <span className="mt-0.5 block text-xs text-slate-200/65">{detail}</span>
                </span>
                <Check
                  aria-hidden="true"
                  className="ml-auto shrink-0 text-emerald-200"
                  size={16}
                />
              </div>
            ))}
          </div>
        </section>

        <div className="relative z-10 flex items-center gap-2 text-sm text-slate-200/70">
          <BellRing aria-hidden="true" className="text-emerald-200" size={17} />
          Queue updates stream securely to your device.
        </div>
      </aside>
    </main>
  );
}
