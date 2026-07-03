// Entry glue (excluded from coverage): mounts the overlay and picks its bridge.
// Inside the Tauri shell it uses the real IPC bridge and re-dispatches the host's
// `cortex:activate` event (emitted on the global hotkey) to the DOM event the
// overlay listens on; in a plain browser (`vite dev`) it uses the demo bridge and
// self-summons so the design is visible immediately.
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { DemoBridge } from "./bridge/demoBridge";
import { TauriBridge } from "./bridge/tauriBridge";
import type { BrainBridge } from "./bridge/types";
import { App } from "./components/App";
import "./overlay.css";

const inTauri = "__TAURI_INTERNALS__" in window;

const root = document.getElementById("root");
if (root) {
  const bridge: BrainBridge = inTauri ? new TauriBridge() : new DemoBridge();
  const sessionId = inTauri ? crypto.randomUUID() : "dev";
  createRoot(root).render(
    <StrictMode>
      <App bridge={bridge} sessionId={sessionId} />
    </StrictMode>,
  );
  if (inTauri) {
    void import("@tauri-apps/api/event").then(({ listen }) =>
      listen("cortex:activate", () => window.dispatchEvent(new Event("cortex:activate"))),
    );
  } else {
    // Defer so App's activate listener is attached: effects flush before paint, so two animation
    // frames are safely past them (setTimeout(0) raced StrictMode's mount-unmount-remount cycle).
    requestAnimationFrame(() =>
      requestAnimationFrame(() => window.dispatchEvent(new Event("cortex:activate"))),
    );
  }
}
