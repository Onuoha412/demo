import { Link } from "react-router-dom";

import { PageContainer } from "../../components/common/PageContainer";

export function HomePage() {
  return (
    <PageContainer className="py-20">
      <h1 className="text-5xl font-black tracking-tight text-ink">QueueLess Customer App</h1>
      <p className="mt-5 max-w-2xl text-lg text-ink/70">
        Join queues remotely, monitor your position, and arrive exactly when your
        turn is called.
      </p>
      <div className="mt-8 flex gap-3">
        <Link to="/services" className="rounded-full bg-ink px-6 py-3 text-white">
          Explore services
        </Link>
        <Link to="/register" className="rounded-full border border-ink/20 px-6 py-3 text-ink">
          Create account
        </Link>
      </div>
    </PageContainer>
  );
}
