/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The overlay must reach 100% coverage. Two files are excluded below: `main.tsx` is entry glue,
// and `tauriBridge.ts` does nothing but cross the Tauri IPC boundary, which CI cannot run.
export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  server: {
    port: 5173,
    strictPort: true,
    // Tauri writes the Rust build output under src-tauri/target. If Vite's HMR watcher follows
    // it, the watcher crashes with EBUSY when cargo relinks the .dll.
    watch: { ignored: ["**/src-tauri/**"] },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    // Files and tests run in a shuffled but fixed order, so it is not the declaration order and
    // is the same twice. The number is arbitrary; `just shuffle` runs other seeds.
    sequence: { shuffle: true, seed: 65537 },
    coverage: {
      provider: "v8",
      all: true,
      include: ["src/**/*.{ts,tsx}"],
      exclude: [
        "src/**/*.test.{ts,tsx}",
        "src/main.tsx",
        "src/bridge/tauriBridge.ts",
        "src/overlay/canvasPicture.ts",
        "src/test-setup.ts",
        "src/vite-env.d.ts",
      ],
      reporter: ["text", "json-summary"],
      thresholds: { lines: 100, branches: 100, functions: 100, statements: 100 },
    },
  },
});
