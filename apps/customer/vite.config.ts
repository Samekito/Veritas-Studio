/// <reference types="vitest/config" />
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Consume the shared package's TS source directly (workspace, no build step).
const shared = fileURLToPath(new URL("../../packages/shared/src", import.meta.url));

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@veritas/shared": shared },
  },
  server: {
    port: 5173,
    // Proxy API calls to the FastAPI backend during local dev.
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setup.ts",
  },
});
