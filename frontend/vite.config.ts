import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  const apiUrl = env.VITE_API_URL || "http://localhost:8000";
  return {
    plugins: [react()],
    test: {
      environment: "jsdom",
      setupFiles: "./src/test/setup.ts",
      globals: true,
    },
    server: {
      port: 5173,
      host: true,
      proxy: {
        "/api": apiUrl,
        "/health": apiUrl,
        "/ws": {
          target: apiUrl.replace(/^http/, "ws"),
          ws: true
        }
      }
    }
  };
});
