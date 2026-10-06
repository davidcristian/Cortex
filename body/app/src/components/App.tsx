import { type MouseEvent, useEffect } from "react";

import { NO_CLIPBOARD, NO_DROPS } from "../bridge/clipboard";
import type { BrainBridge, HostClipboard, HostDrops, OverlayWindow } from "../bridge/types";
import { resolveEdge } from "../edge/edges";
import { resolveMark } from "../mark/marks";
import { ACTIVATE_EVENT, TOGGLE_EVENT, takePendingActivation } from "../overlay/activation";
import { guardDrops } from "../overlay/dropGuard";
import { useOverlay } from "../overlay/useOverlay";
import { NO_WINDOW, useOverlayWindow } from "../overlay/useOverlayWindow";
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
  /** The OS window the overlay draws in; the browser build has none. */
  readonly osWindow?: OverlayWindow;
  /** The host clipboard a paste with no file reads; the browser build has none. */
  readonly clipboard?: HostClipboard;
  /** The host's native drops, for a webview that gives the page no dropped file; the browser
   *  build has none. */
  readonly drops?: HostDrops;
}

/** Connects the appearance settings read from the brain, and host activation, to the overlay
 *  controller. */
export function App({
  bridge,
  newSessionId,
  osWindow = NO_WINDOW,
  clipboard = NO_CLIPBOARD,
  drops = NO_DROPS,
}: AppProps) {
  const controller = useOverlay(bridge, newSessionId, undefined, clipboard, drops);
  useOverlayWindow(controller.state.mode, osWindow);
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

  useEffect(() => guardDrops(window), []);

  // The composer takes a native drop that ends over it, as it takes a page drop.
  const dropPictures = controller.dropPictures;
  useEffect(
    () =>
      drops.listen((x, y) => {
        if (document.elementFromPoint(x, y)?.closest(".composer")) {
          dropPictures();
        }
      }),
    [drops, dropPictures],
  );

  useEffect(() => {
    const toggle = controller.toggle;
    window.addEventListener(TOGGLE_EVENT, toggle);
    return () => window.removeEventListener(TOGGLE_EVENT, toggle);
  }, [controller.toggle]);

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
