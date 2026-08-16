/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The overlay is gated at 100% (ADR-0011 addendum). Coverage covers every component, every pure
// module, and both `BrainBridge` implementations that CI can run: the fake and the browser-dev
// demo bridge, driven over one shared check list (src/bridge/bridgeContract.ts) plus the demo's
// own suite for the conversation it scripts, its script measured with it.
// Two files stay out, each for a reason a test cannot remove. `main.tsx` is entry glue. And
// `tauriBridge.ts` crosses the Tauri IPC boundary on every call, which makes it the frontend
// analog of the Rust host adapters: host-validated, never in CI (AGENTS.md gate 3), and holding
// nothing but that crossing, since every branchy turn decision lives in the gated core.
export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  server: {
    port: 5173,
    strictPort: true,
    // Tauri writes the Rust build output under src-tauri/target; if Vite's HMR
    // watcher follows it, it crashes with EBUSY when cargo relinks the .dll.
    watch: { ignored: ["**/src-tauri/**"] },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    // Files and tests run shuffled under a FIXED seed, so the order is not the declaration
    // order and is still the same order twice (ADR-0002 shuffle addendum). The number is
    // arbitrary and frozen: changing it reshuffles this suite for no reason, and it differs
    // from the two Python suites' seeds on purpose, so nobody reads three independent numbers
    // as one value that has to agree. `just shuffle` is the deliberate sweep over other seeds.
    sequence: { shuffle: true, seed: 65537 },
    coverage: {
      provider: "v8",
      all: true,
      include: ["src/**/*.{ts,tsx}"],
      exclude: [
        "src/**/*.test.{ts,tsx}",
        "src/main.tsx",
        "src/bridge/tauriBridge.ts",
        "src/test-setup.ts",
        "src/vite-env.d.ts",
      ],
      reporter: ["text", "json-summary"],
      thresholds: { lines: 100, branches: 100, functions: 100, statements: 100 },
    },
  },
});
