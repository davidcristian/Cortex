import { type MouseEvent, useEffect } from "react";

import type { BrainBridge } from "../bridge/types";
import { resolveMark } from "../mark/marks";
import { useOverlay } from "../overlay/useOverlay";
import { usePreferences } from "../overlay/usePreferences";
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

/** Wires the appearance (theme + mark, hydrated from the brain's settings record, ADR-0032) and
 *  host activation to the overlay controller. */
export function App({ bridge, newSessionId }: AppProps) {
  const controller = useOverlay(bridge, newSessionId);
  const { appearance, setTheme, setMark } = usePreferences(bridge);
  const theme = resolveTheme(appearance.theme, systemPrefersDark());
  const mark = resolveMark(appearance.mark);

  useEffect(() => {
    applyTheme(theme, document.documentElement);
  }, [theme]);

  // The host (the Tauri global hotkey) summons the overlay via a window event.
  useEffect(() => {
    const summon = () => controller.open();
    window.addEventListener("cortex:activate", summon);
    return () => window.removeEventListener("cortex:activate", summon);
  }, [controller.open]);

  // The header's quick flip names the opposite theme outright, so it always lands somewhere
  // definite; going back to "follow the system" is the settings sheet's job (it can express the
  // `null` the toggle cannot).
  const toggleTheme = () => setTheme(theme.scheme === "dark" ? "daylight" : "midnight");

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
      <Overlay
        controller={controller}
        dark={theme.scheme === "dark"}
        themeName={appearance.theme}
        mark={mark}
        onPickTheme={setTheme}
        onPickMark={setMark}
        onToggleTheme={toggleTheme}
      />
    </div>
  );
}
