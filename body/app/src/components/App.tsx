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
  /** The factory for new chat ids. Tests set their own; production uses the default uuid. */
  readonly newSessionId?: () => string;
}

/** Connects the appearance settings read from the brain, and host activation, to the overlay
 *  controller. */
export function App({ bridge, newSessionId }: AppProps) {
  const controller = useOverlay(bridge, newSessionId);
  const { appearance, setTheme, setMark, setWindow } = usePreferences(bridge);
  const theme = resolveTheme(appearance.theme, systemPrefersDark());
  const mark = resolveMark(appearance.mark);
  const edge = resolveEdge(appearance.window);

  useEffect(() => {
    applyTheme(theme, document.documentElement);
  }, [theme]);

  // An activation that arrived before this listener existed is kept as a pending request, so a
  // hotkey press during startup still opens the overlay instead of being dropped.
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

  const toggleTheme = () => setTheme(theme.scheme === "dark" ? "daylight" : "midnight");

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
