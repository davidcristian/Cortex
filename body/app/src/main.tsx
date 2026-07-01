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
    // Defer so App's activate listener is attached (effects run after first render).
    setTimeout(() => window.dispatchEvent(new Event("cortex:activate")), 0);
  }
}
