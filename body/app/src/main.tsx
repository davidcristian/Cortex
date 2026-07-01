// Entry glue (excluded from coverage): mounts the overlay for `vite dev` with the browser-dev
// bridge and summons it once so the design is visible immediately. Production mounts via Tauri.
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { DemoBridge } from "./bridge/demoBridge";
import { App } from "./components/App";
import "./overlay.css";

const root = document.getElementById("root");
if (root) {
  createRoot(root).render(
    <StrictMode>
      <App bridge={new DemoBridge()} sessionId="dev" />
    </StrictMode>,
  );
  window.dispatchEvent(new Event("cortex:activate"));
}
