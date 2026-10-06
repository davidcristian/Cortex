// Mounts the overlay. Inside the Tauri shell it uses the real bridge, window and clipboard, and
// forwards the host's `cortex:activate` and `cortex:toggle` events as DOM events; in a plain
// browser it uses the demo bridge and summons itself. Excluded from coverage.
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { NO_CLIPBOARD } from "./bridge/clipboard";
import { DemoBridge } from "./bridge/demoBridge";
import { TauriBridge, TauriClipboard, TauriWindow } from "./bridge/tauriBridge";
import type { BrainBridge } from "./bridge/types";
import { App } from "./components/App";
import { TOGGLE_EVENT, requestActivation } from "./overlay/activation";
import { NO_WINDOW } from "./overlay/useOverlayWindow";
import "./overlay.css";

const inTauri = "__TAURI_INTERNALS__" in window;

const root = document.getElementById("root");
if (root) {
  const bridge: BrainBridge = inTauri ? new TauriBridge() : new DemoBridge();
  const osWindow = inTauri ? new TauriWindow() : NO_WINDOW;
  const clipboard = inTauri ? new TauriClipboard() : NO_CLIPBOARD;
  createRoot(root).render(
    <StrictMode>
      <App bridge={bridge} osWindow={osWindow} clipboard={clipboard} />
    </StrictMode>,
  );
  if (inTauri) {
    void import("@tauri-apps/api/event").then(({ listen }) =>
      Promise.all([
        listen("cortex:activate", requestActivation),
        listen(TOGGLE_EVENT, () => window.dispatchEvent(new Event(TOGGLE_EVENT))),
      ]),
    );
  } else {
    // Deferring this does not help: passive effects flush after paint, so it always ran before
    // App's listener existed. `requestActivation` records the request and the listener takes it
    // when it attaches.
    requestActivation();
  }
}
