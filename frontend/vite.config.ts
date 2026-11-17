import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode, command }) => {
  const env = loadEnv(mode, ".", "");
  const localBuild =
    command === "build" &&
    process.env.CI !== "true" &&
    process.env.GITHUB_ACTIONS !== "true";
  const localApiUrl = "http://localhost:8000";
  const apiUrl =
    env.VITE_API_URL ||
    (command === "serve" || localBuild ? localApiUrl : "");
  const wsUrl =
    env.VITE_WS_URL ||
    (command === "serve" || localBuild ? apiUrl.replace(/^http/, "ws") : "");
  if (command === "build") {
    let api: URL;
    let websocket: URL;
    try {
      api = new URL(apiUrl);
      websocket = new URL(wsUrl);
    } catch {
      throw new Error(
        "Builds require VITE_API_URL and VITE_WS_URL. Configure HTTPS/WSS URLs for deployment, or use the localhost defaults for a local preview.",
      );
    }

    const isLocalHost = (hostname: string) =>
      ["localhost", "127.0.0.1", "[::1]"].includes(
        hostname.toLowerCase().replace(/^\[|\]$/g, ""),
      );
    const localEndpoints =
      isLocalHost(api.hostname) && isLocalHost(websocket.hostname);
    const isPlaceholderHost = (hostname: string) => {
      const normalized = hostname.toLowerCase().replace(/^\[|\]$/g, "");
      return (
        isLocalHost(normalized) ||
        normalized.endsWith(".invalid") ||
        normalized.endsWith(".test") ||
        normalized.endsWith(".localhost") ||
        normalized.endsWith(".example")
      );
    };

    const hasInvalidOrigin =
      (localEndpoints
        ? api.protocol !== "http:" || websocket.protocol !== "ws:"
        : api.protocol !== "https:" || websocket.protocol !== "wss:") ||
      api.username ||
      api.password ||
      websocket.username ||
      websocket.password ||
      (!isPlaceholderHost(api.hostname) &&
        !api.hostname.includes(".")) ||
      (!isPlaceholderHost(websocket.hostname) &&
        !websocket.hostname.includes("."));

    if (hasInvalidOrigin) {
      throw new Error(
        "Production builds require public HTTPS API and WSS endpoints.",
      );
    }
  }
  const repositoryName = process.env.GITHUB_REPOSITORY?.split("/")[1];
  const configuredBase = env.VITE_BASE_PATH?.trim();
  if (
    configuredBase &&
    (!configuredBase.startsWith("/") ||
      configuredBase.startsWith("//") ||
      /[?#]/.test(configuredBase))
  ) {
    throw new Error("VITE_BASE_PATH must be a root-relative path without query or hash");
  }
  const base = configuredBase
    ? `${configuredBase.replace(/\/+$/, "")}/`
    : process.env.GITHUB_ACTIONS === "true" &&
        repositoryName &&
        !repositoryName.endsWith(".github.io")
    ? `/${repositoryName}/`
    : "/";
  return {
    base,
    define:
      command === "build"
        ? {
            "import.meta.env.VITE_API_URL": JSON.stringify(apiUrl),
            "import.meta.env.VITE_WS_URL": JSON.stringify(wsUrl),
          }
        : undefined,
    plugins: [react()],
    build: {
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (!id.includes("/node_modules/")) return;
            if (
              id.includes("/@sentry/") ||
              id.includes("/posthog-js/") ||
              id.includes("/@posthog/")
            ) {
              return "monitoring";
            }
            if (
              id.includes("/react/") ||
              id.includes("/react-dom/") ||
              id.includes("/react-router/") ||
              id.includes("/react-router-dom/") ||
              id.includes("/scheduler/") ||
              id.includes("/@remix-run/router/")
            ) {
              return "react-vendor";
            }
            if (id.includes("/@tanstack/")) return "query-vendor";
            if (id.includes("/lucide-react/")) return "icons";
            if (
              id.includes("/recharts/") ||
              id.includes("/d3-") ||
              id.includes("/victory-vendor/")
            ) {
              return "charts";
            }
          },
        },
      },
    },
    test: {
      environment: "jsdom",
      environmentOptions: {
        jsdom: { url: "http://localhost:5173" },
      },
      setupFiles: "./src/test/setup.ts",
      globals: true,
    },
    server: {
      port: 5173,
      host: true,
      proxy: {
        "/api": apiUrl,
        "/health": apiUrl,
        "/ready": apiUrl,
        "/ws": {
          target: apiUrl.replace(/^http/, "ws"),
          ws: true
        }
      }
    }
  };
});
