/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The overlay is gated at 100% (ADR-0011 addendum). Coverage covers every
// component and pure module; excluded are the entry glue (main.tsx) and the
// real Tauri bridge (tauriBridge.ts), which is the frontend analog of the Rust host
// adapters, validated on the host, not in CI.
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
    coverage: {
      provider: "v8",
      all: true,
      include: ["src/**/*.{ts,tsx}"],
      exclude: [
        "src/**/*.test.{ts,tsx}",
        "src/main.tsx",
        "src/bridge/tauriBridge.ts",
        "src/bridge/demoBridge.ts",
        "src/bridge/demoScript.ts",
        "src/test-setup.ts",
        "src/vite-env.d.ts",
      ],
      reporter: ["text", "json-summary"],
      thresholds: { lines: 100, branches: 100, functions: 100, statements: 100 },
    },
  },
});
