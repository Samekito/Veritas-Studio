import { defineConfig } from "vitest/config";

// The shared client is environment-agnostic; run its tests in Node.
export default defineConfig({
  test: { environment: "node" },
});
