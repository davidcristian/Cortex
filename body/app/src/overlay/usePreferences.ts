import { useCallback, useEffect, useRef, useState } from "react";

import type { BrainBridge } from "../bridge/types";

// The user's appearance choices, read from the brain's settings record once and written back on
// every change. The record is the brain's, so a choice outlives this window.

/** The record's keys, namespaced because the record is shared with every future surface. */
export const THEME_KEY = "overlay.theme";
export const MARK_KEY = "overlay.mark";
export const WINDOW_KEY = "overlay.window";

/** The three appearance choices, each `null` when the user has not made one (the default applies:
 *  the system colour scheme for the theme, the default bubble for the mark, the default edge for
 *  the window). */
export interface Appearance {
  readonly theme: string | null;
  readonly mark: string | null;
  readonly window: string | null;
}

export interface AppearanceController {
  readonly appearance: Appearance;
  /** Choose a theme by name, or `null` to follow the system scheme again (clears the key). */
  setTheme: (name: string | null) => void;
  /** Choose a mark style by name. */
  setMark: (name: string) => void;
  /** Choose a window edge style by name (ADR-0036). */
  setWindow: (name: string) => void;
}

const NOTHING_CHOSEN: Appearance = { theme: null, mark: null, window: null };

/** Read the appearance from the brain once, and save every later change. The write is optimistic:
 *  the choice applies to this render and the call is not awaited, so a slow brain cannot make
 *  picking a theme feel stuck. The `chosen` latch keeps a choice made before the record arrives. */
export function usePreferences(bridge: BrainBridge): AppearanceController {
  const [appearance, setAppearance] = useState<Appearance>(NOTHING_CHOSEN);
  const chosen = useRef({ theme: false, mark: false, window: false });

  useEffect(() => {
    let live = true;
    bridge
      .getPreferences()
      .then((stored) => {
        if (!live) {
          return;
        }
        const read = (key: string): string | null =>
          stored.find((pref) => pref.key === key)?.value ?? null;
        setAppearance((current) => ({
          theme: chosen.current.theme ? current.theme : read(THEME_KEY),
          mark: chosen.current.mark ? current.mark : read(MARK_KEY),
          window: chosen.current.window ? current.window : read(WINDOW_KEY),
        }));
      })
      .catch(() => {
        // A brain that cannot be reached leaves the defaults in place, which is a first run.
      });
    return () => {
      live = false;
    };
  }, [bridge]);

  const write = useCallback(
    (key: string, value: string) => {
      bridge.setPreference(key, value).catch(() => {
        // Not fatal: the choice is already applied above, and only its durability is lost.
      });
    },
    [bridge],
  );

  const setTheme = useCallback(
    (name: string | null) => {
      chosen.current.theme = true;
      setAppearance((current) => ({ ...current, theme: name }));
      // `null` means "follow the system", which the record writes as a cleared key.
      write(THEME_KEY, name ?? "");
    },
    [write],
  );

  const setMark = useCallback(
    (name: string) => {
      chosen.current.mark = true;
      setAppearance((current) => ({ ...current, mark: name }));
      write(MARK_KEY, name);
    },
    [write],
  );

  const setWindow = useCallback(
    (name: string) => {
      chosen.current.window = true;
      setAppearance((current) => ({ ...current, window: name }));
      write(WINDOW_KEY, name);
    },
    [write],
  );

  return { appearance, setTheme, setMark, setWindow };
}
