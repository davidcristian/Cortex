// Entry glue: mounts the overlay. Excluded from coverage (the browser bootstrap
// analog of the Rust __main__ guard); the Overlay component itself is gated.
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

const root = document.getElementById("root");
if (root) {
  createRoot(root).render(
    <StrictMode>
      <div>Cortex overlay</div>
    </StrictMode>,
  );
}
