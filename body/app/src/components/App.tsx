import { type MouseEvent, useEffect } from "react";

import type { BrainBridge } from "../bridge/types";
import { resolveEdge } from "../edge/edges";
import { resolveMark } from "../mark/marks";
import { ACTIVATE_EVENT, takePendingActivation } from "../overlay/activation";
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
  const { appearance, setTheme, setMark, setWindow } = usePreferences(bridge);
  const theme = resolveTheme(appearance.theme, systemPrefersDark());
  const mark = resolveMark(appearance.mark);
  const edge = resolveEdge(appearance.window);

  useEffect(() => {
    applyTheme(theme, document.documentElement);
  }, [theme]);

  // The host (the Tauri global hotkey) summons the overlay through a window event. An activation
  // that arrived before this listener existed is held as a pending request, so a hotkey press
  // during a cold start, and the browser build's self-summon on load, which always arrives first,
  // still open the overlay instead of being dropped. Both paths consume the request.
  useEffect(() => {
    const summon = () => {
      takePendingActivation();
      controller.open();
    };
    window.addEventListener(ACTIVATE_EVENT, summon);
    if (takePendingActivation()) {
      controller.open();
    }
    return () => window.removeEventListener(ACTIVATE_EVENT, summon);
  }, [controller.open]);

  // The header's toggle names the opposite theme outright, so it always lands on a specific theme.
  // Going back to "follow the system" belongs to the console's appearance tab, which is the only
  // place that can set the `null` the toggle cannot express.
  const toggleTheme = () => setTheme(theme.scheme === "dark" ? "daylight" : "midnight");

  // Click-away dismisses (design/overlay-ux.md §4): a press on the bare stage around the open panel
  // does what Esc does. Presses inside the panel, or on the orb and preview, which handle their own
  // clicks, arrive here with a different target and pass through.
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
        edge={edge}
        onPickTheme={setTheme}
        onPickMark={setMark}
        onPickEdge={setWindow}
        onToggleTheme={toggleTheme}
      />
    </div>
  );
}
