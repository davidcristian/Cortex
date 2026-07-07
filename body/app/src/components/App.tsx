import { useEffect, useState } from "react";

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

  return (
    <div className="stage">
      <Overlay controller={controller} dark={theme.scheme === "dark"} onToggleTheme={toggleTheme} />
    </div>
  );
}
