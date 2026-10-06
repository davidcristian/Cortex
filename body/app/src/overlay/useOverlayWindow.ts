import { useEffect, useRef } from "react";

import type { OverlayWindow } from "../bridge/types";
import type { Mode } from "./overlayState";

/** How long a hide waits, matching `.panel`'s 0.3s opacity transition in overlay.css, so that a
 *  dismissed panel fades out before its window goes. */
export const WINDOW_HIDE_MS = 300;

/** A window with nothing behind it, for the browser build, where the page is the whole surface. */
export const NO_WINDOW: OverlayWindow = { setShown: () => undefined };

/** Keep the OS window shown exactly while the overlay has something on screen. The window starts
 *  hidden, and a summon that the overlay sees again before its hide has run cancels the hide. */
export function useOverlayWindow(mode: Mode, osWindow: OverlayWindow): void {
  const shown = mode !== "hidden";
  const told = useRef(false);
  useEffect(() => {
    if (shown === told.current) {
      return undefined;
    }
    if (shown) {
      told.current = true;
      osWindow.setShown(true);
      return undefined;
    }
    const timer = setTimeout(() => {
      told.current = false;
      osWindow.setShown(false);
    }, WINDOW_HIDE_MS);
    return () => clearTimeout(timer);
  }, [shown, osWindow]);
}
