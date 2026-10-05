import { BrowserRouter, Link, Route, Routes } from "react-router-dom";
import { ArrowRight, Clock3, Menu, ShieldCheck, UsersRound, X } from "lucide-react";
import { useState } from "react";
import type { ReactNode } from "react";

import { Button } from "./components/common/Button";
import { PageContainer } from "./components/common/PageContainer";

const placeholderRoutes = [
  { path: "/login", title: "Welcome back", description: "Customer sign-in is ready for the next stage." },
  { path: "/register", title: "Join QueueLess", description: "Account creation will be connected to authentication next." },
  { path: "/services", title: "Explore services", description: "Service discovery and queue joining are coming next." },
  { path: "/staff/login", title: "Staff portal", description: "Staff tools will appear here in the next stage." },
  { path: "/admin/login", title: "Admin portal", description: "Administration tools will appear here in the next stage." }
];

function Header() {
  const [open, setOpen] = useState(false);
  return (
    <header className="border-b border-ink/10 bg-cream/90 backdrop-blur">
      <PageContainer className="flex h-20 items-center justify-between">
        <Link to="/" className="text-2xl font-black tracking-tight text-ink" onClick={() => setOpen(false)}>
          Queue<span className="text-emerald-700">Less</span>
        </Link>
        <nav className="hidden items-center gap-8 md:flex" aria-label="Main navigation">
          <Link className="font-medium text-ink/70 hover:text-ink" to="/services">Services</Link>
          <Link className="font-medium text-ink/70 hover:text-ink" to="/login">Sign in</Link>
          <Button as={Link} to="/register">Get started <ArrowRight size={16} /></Button>
        </nav>
        <button className="rounded-lg p-2 text-ink md:hidden" aria-label={open ? "Close menu" : "Open menu"} onClick={() => setOpen(!open)}>
          {open ? <X /> : <Menu />}
        </button>
      </PageContainer>
      {open && <nav className="space-y-1 border-t border-ink/10 px-6 py-4 md:hidden" aria-label="Mobile navigation">
        <Link className="block rounded-lg px-3 py-2 text-ink" to="/services" onClick={() => setOpen(false)}>Services</Link>
        <Link className="block rounded-lg px-3 py-2 text-ink" to="/login" onClick={() => setOpen(false)}>Sign in</Link>
        <Link className="block rounded-lg px-3 py-2 font-semibold text-emerald-800" to="/register" onClick={() => setOpen(false)}>Get started</Link>
      </nav>}
    </header>
  );
}

function HomePage() {
  return <div className="min-h-screen bg-cream text-ink">
    <Header />
    <main>
      <section className="overflow-hidden">
        <PageContainer className="grid gap-14 py-20 md:grid-cols-[1.1fr_.9fr] md:items-center md:py-28">
          <div>
            <div className="mb-6 inline-flex items-center gap-2 rounded-full bg-mint/60 px-4 py-2 text-sm font-semibold">
              <span className="h-2 w-2 rounded-full bg-emerald-700" /> A better way to wait
            </div>
            <h1 className="max-w-3xl text-6xl font-black leading-[.95] tracking-[-.06em] sm:text-7xl lg:text-8xl">
              Your time is <span className="text-emerald-700">yours.</span>
            </h1>
            <p className="mt-8 max-w-xl text-lg leading-8 text-ink/65 sm:text-xl">
              Join a virtual queue, keep your place, and get on with your day. QueueLess makes every wait clear, calm, and predictable.
            </p>
            <div className="mt-10 flex flex-wrap gap-4">
              <Button as={Link} to="/services">Find a service <ArrowRight size={18} /></Button>
              <Button as={Link} to="/staff/login" variant="secondary">Staff portal</Button>
            </div>
          </div>
          <div className="relative">
            <div className="rounded-[2rem] bg-ink p-6 text-cream shadow-2xl shadow-emerald-950/20 sm:p-8">
              <div className="flex items-center justify-between border-b border-cream/15 pb-5">
                <div><p className="text-sm text-cream/60">Your queue status</p><p className="mt-1 text-xl font-bold">Downtown Clinic</p></div>
                <span className="rounded-full bg-mint px-3 py-1 text-xs font-bold text-ink">LIVE</span>
              </div>
              <div className="py-10 text-center"><p className="text-sm text-cream/60">Now serving</p><p className="mt-2 text-7xl font-black text-mint">A24</p><p className="mt-3 text-cream/60">Your number <strong className="text-cream">A31</strong></p></div>
              <div className="grid grid-cols-2 gap-3"><div className="rounded-xl bg-cream/10 p-4"><Clock3 size={18} className="text-mint" /><p className="mt-3 text-2xl font-bold">18 min</p><p className="text-xs text-cream/60">Estimated wait</p></div><div className="rounded-xl bg-cream/10 p-4"><UsersRound size={18} className="text-mint" /><p className="mt-3 text-2xl font-bold">7th</p><p className="text-xs text-cream/60">In line</p></div></div>
            </div>
          </div>
        </PageContainer>
      </section>
      <section className="border-y border-ink/10 bg-white/50 py-16">
        <PageContainer><p className="text-center text-sm font-bold uppercase tracking-[.2em] text-ink/45">Designed for less waiting, everywhere</p><div className="mt-10 grid gap-5 md:grid-cols-3"><Feature icon={<Clock3 />} title="Know your time" text="Clear, live estimates let you plan your day with confidence." /><Feature icon={<ShieldCheck />} title="Keep your place" text="Your spot is secure and visible from the moment you join." /><Feature icon={<UsersRound />} title="Serve with ease" text="A simple staff experience keeps every queue moving." /></div></PageContainer>
      </section>
    </main>
    <footer className="py-8"><PageContainer className="flex flex-col justify-between gap-3 text-sm text-ink/50 sm:flex-row"><span>© 2026 QueueLess</span><span>Less waiting. More living.</span></PageContainer></footer>
  </div>;
}

function Feature({ icon, title, text }: { icon: ReactNode; title: string; text: string }) {
  return <article className="rounded-2xl border border-ink/10 bg-cream p-6"><div className="mb-5 inline-flex rounded-xl bg-mint p-3 text-ink">{icon}</div><h2 className="text-xl font-bold">{title}</h2><p className="mt-2 leading-7 text-ink/60">{text}</p></article>;
}

function PlaceholderPage({ title, description }: { title: string; description: string }) {
  return <div className="min-h-screen bg-cream text-ink"><Header /><PageContainer className="py-28"><p className="font-semibold text-emerald-700">QueueLess</p><h1 className="mt-4 text-5xl font-black tracking-tight">{title}</h1><p className="mt-5 max-w-lg text-lg text-ink/60">{description}</p><Button as={Link} to="/" className="mt-8">Back home</Button></PageContainer></div>;
}

export default function App() {
  return <BrowserRouter><Routes><Route path="/" element={<HomePage />} />{placeholderRoutes.map((route) => <Route key={route.path} path={route.path} element={<PlaceholderPage title={route.title} description={route.description} />} />)}<Route path="*" element={<PlaceholderPage title="Page not found" description="That page does not exist. Let's get you back on track." />} /></Routes></BrowserRouter>;
}
