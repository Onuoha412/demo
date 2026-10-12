import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

const slides = [
  {
    badge: "REAL-TIME QUEUE",
    title: "Skip the waiting. Join the queue digitally.",
    number: "A024",
    detail: "3 people ahead",
    eta: "~ 8 min",
  },
  {
    badge: "YOUR PLACE",
    title: "Know your place in line.",
    number: "A024",
    detail: "You are next up soon",
    eta: "2 spots left",
  },
  {
    badge: "LIVE UPDATES",
    title: "Get called in real time.",
    number: "A021",
    detail: "Now serving",
    eta: "Service desk 2",
  },
  {
    badge: "ONE QUEUE",
    title: "One queue. Less waiting.",
    number: "QR",
    detail: "Scan and track",
    eta: "Fast check-in",
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
  const [activeSlide, setActiveSlide] = useState(0);

  useEffect(() => {
    const mediaQueryList =
      typeof window !== "undefined" && typeof window.matchMedia === "function"
        ? window.matchMedia("(prefers-reduced-motion: reduce)")
        : null;

    if (mediaQueryList?.matches) return;

    const timer = window.setInterval(() => {
      setActiveSlide((current) => (current + 1) % slides.length);
    }, 4200);

    return () => window.clearInterval(timer);
  }, []);

  const slide = slides[activeSlide];

  return (
    <main className="mx-auto grid min-h-[calc(100vh-4rem)] max-w-7xl items-stretch gap-8 px-4 py-8 lg:grid-cols-[1.08fr_0.92fr] lg:px-8">
      <section className="flex items-center justify-center">
        <div className="w-full max-w-lg rounded-[2rem] border border-slate-200/80 bg-white/90 p-6 shadow-[0_30px_80px_rgba(15,23,42,0.10)] backdrop-blur-sm sm:p-10">
          <Link to="/" className="inline-flex items-center gap-3 text-xl font-black tracking-[-0.04em] text-slate-900">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-100 text-lg text-emerald-700 shadow-inner">
              Q
            </span>
            Queue<span className="text-emerald-700">Less</span>
          </Link>

          <p className="mt-8 text-xs font-bold uppercase tracking-[0.22em] text-emerald-700">
            Queue smarter
          </p>
          <h1 className="mt-2 text-4xl font-black tracking-[-0.06em] text-slate-900">{title}</h1>
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
            <span className="inline-block h-2 w-2 rounded-full bg-emerald-300" /> QueueLess
          </span>
          <span className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 py-1.5">
            <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-300" /> Live
          </span>
        </div>

        <div className="relative z-10">
          <p className="text-xs font-bold uppercase tracking-[0.28em] text-emerald-200/90">{slide.badge}</p>
          <h2 className="mt-4 max-w-lg text-4xl font-black leading-tight tracking-[-0.08em] text-white">
            {slide.title}
          </h2>
          <p className="mt-4 max-w-md text-base text-slate-200/80">
            Keep your place, track the wait, and get notified the moment it’s your turn.
          </p>
        </div>

        <div className="relative z-10 mx-auto w-full max-w-md">
          <div className="auth-ticket-card rounded-[1.6rem] border border-white/15 bg-white/9 p-6 shadow-[0_20px_50px_rgba(16,185,129,0.2)] backdrop-blur-lg">
            <div className="flex items-center justify-between text-[11px] font-semibold uppercase tracking-[0.24em] text-emerald-100/80">
              <span>Ticket</span>
              <span>{slide.badge}</span>
            </div>

            <div className="mt-6 flex items-end justify-between gap-4">
              <div>
                <p className="text-sm text-slate-200/70">Your number</p>
                <p className="mt-2 text-5xl font-black tracking-[-0.08em] text-white">{slide.number}</p>
              </div>
              <div className="rounded-full bg-emerald-300 px-3 py-2 text-sm font-bold text-slate-900 shadow-lg shadow-emerald-900/20">
                {slide.detail}
              </div>
            </div>

            <div className="mt-6 h-2.5 overflow-hidden rounded-full bg-white/10">
              <div className="h-full w-2/3 rounded-full bg-gradient-to-r from-emerald-300 via-emerald-200 to-lime-300" />
            </div>

            <div className="mt-4 flex items-center justify-between text-sm text-slate-200/80">
              <span>{slide.eta}</span>
              <span>Estimated wait</span>
            </div>
          </div>

          <div className="auth-float-card absolute -right-4 -top-7 rounded-2xl border border-emerald-200/30 bg-white px-4 py-3 text-sm font-semibold text-slate-800 shadow-xl">
            <span className="mr-2 text-emerald-600">●</span>
            {slide.detail}
          </div>
        </div>

        <div className="relative z-10 flex items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-sm text-slate-200/70">
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-300" />
            Queue updates stream securely to your device
          </div>
          <div className="flex items-center gap-2">
            {slides.map((_, index) => (
              <button
                key={slides[index].badge}
                type="button"
                aria-label={`Show slide ${index + 1}`}
                className={`h-2.5 rounded-full transition-all ${
                  index === activeSlide ? "w-8 bg-emerald-300" : "w-2.5 bg-white/30 hover:bg-white/60"
                }`}
                onClick={() => setActiveSlide(index)}
              />
            ))}
          </div>
        </div>
      </aside>
    </main>
  );
}
