import { Component, StrictMode } from "react";
import type { ErrorInfo, ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import "./styles.css";
import "./observability";

class AppErrorBoundary extends Component<
  { children: ReactNode },
  { hasError: boolean }
> {
  state = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("QueueLess encountered a rendering error.", error, info);
    if (import.meta.env.VITE_SENTRY_DSN) {
      void import("@sentry/react").then((sentry) => sentry.captureException(error));
    }
  }

  render() {
    if (this.state.hasError) {
      return <p role="alert">Something went wrong. Please reload the page.</p>;
    }
    return this.props.children;
  }
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      staleTime: 15_000,
    },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AppErrorBoundary>
      <QueryClientProvider client={queryClient}><App /></QueryClientProvider>
    </AppErrorBoundary>
  </StrictMode>
);
