import { type MouseEvent, useEffect, useState } from "react";

import type { BrainBridge } from "../bridge/types";
import { useOverlay } from "../overlay/useOverlay";
import { applyTheme, resolveTheme } from "../theme/themes";
import { Overlay } from "./Overlay";

function systemPrefersDark(): boolean {
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

interface AppProps {
  readonly bridge: BrainBridge;
  /** Injects the new-chat id factory (tests pin it); production uses the default uuid. */
  readonly newSessionId?: () => string;
}

/** Wires the theme + host activation to the overlay controller. */
export function App({ bridge, newSessionId }: AppProps) {
  const controller = useOverlay(bridge, newSessionId);
  const [preference, setPreference] = useState<string | null>(null);
  const theme = resolveTheme(preference, systemPrefersDark());

  useEffect(() => {
    applyTheme(theme, document.documentElement);
  }, [theme]);

  // The host (the Tauri global hotkey) summons the overlay via a window event.
  useEffect(() => {
    const summon = () => controller.open();
    window.addEventListener("cortex:activate", summon);
    return () => window.removeEventListener("cortex:activate", summon);
  }, [controller.open]);

  const toggleTheme = () => setPreference(theme.scheme === "dark" ? "daylight" : "midnight");

  // Click-away dismisses (design/overlay-ux.md §4): a press on the bare stage around the open
  // panel is the same gesture as Esc. Presses inside the panel (or on the orb/preview, which
  // own their click) bubble up with a different target and pass through.
  const onStageMouseDown = (event: MouseEvent<HTMLDivElement>) => {
    if (event.target === event.currentTarget && controller.state.mode === "panel") {
      controller.dismiss();
    }
  };

  return (
    <div className="stage" onMouseDown={onStageMouseDown}>
      <Overlay controller={controller} dark={theme.scheme === "dark"} onToggleTheme={toggleTheme} />
    </div>
  );
}
