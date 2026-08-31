// Mounts the overlay and picks its bridge. Inside the Tauri shell it uses the real IPC bridge and
// forwards the host's `cortex:activate` event to the DOM event the overlay listens on; in a plain
// browser it uses the demo bridge and summons itself. Excluded from coverage.
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { DemoBridge } from "./bridge/demoBridge";
import { TauriBridge } from "./bridge/tauriBridge";
import type { BrainBridge } from "./bridge/types";
import { App } from "./components/App";
import { requestActivation } from "./overlay/activation";
import "./overlay.css";

const inTauri = "__TAURI_INTERNALS__" in window;

const root = document.getElementById("root");
if (root) {
  const bridge: BrainBridge = inTauri ? new TauriBridge() : new DemoBridge();
  createRoot(root).render(
    <StrictMode>
      <App bridge={bridge} />
    </StrictMode>,
  );
  if (inTauri) {
    void import("@tauri-apps/api/event").then(({ listen }) =>
      listen("cortex:activate", requestActivation),
    );
  } else {
    // Deferring this does not help: passive effects flush after paint, so it always ran before
    // App's listener existed. `requestActivation` records the request and the listener takes it
    // when it attaches.
    requestActivation();
  }
}
