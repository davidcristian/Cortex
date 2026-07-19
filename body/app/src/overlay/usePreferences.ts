import { useCallback, useEffect, useRef, useState } from "react";

import type { BrainBridge } from "../bridge/types";

/** The record's keys. Namespaced because the record is shared with every future surface. */
export const THEME_KEY = "overlay.theme";
export const MARK_KEY = "overlay.mark";

/** The two appearance choices, each `null` when the user has not made one (the default applies:
 *  the system colour scheme for the theme, the default bubble for the mark). */
export interface Appearance {
  readonly theme: string | null;
  readonly mark: string | null;
}

export interface AppearanceController {
  readonly appearance: Appearance;
  /** Choose a theme by name, or `null` to follow the system scheme again (clears the key). */
  setTheme: (name: string | null) => void;
  /** Choose a mark style by name. */
  setMark: (name: string) => void;
}

const NOTHING_CHOSEN: Appearance = { theme: null, mark: null };

/** Hydrate the appearance from the brain once, and persist every later change. */
export function usePreferences(bridge: BrainBridge): AppearanceController {
  const [appearance, setAppearance] = useState<Appearance>(NOTHING_CHOSEN);
  const chosen = useRef({ theme: false, mark: false });

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
        }));
      })
      .catch(() => {
        // A brain that cannot be reached leaves the defaults in place, which is exactly what a
        // first run shows. The overlay is usable without its record; only durability is lost.
      });
    return () => {
      live = false;
    };
  }, [bridge]);

  const write = useCallback(
    (key: string, value: string) => {
      bridge.setPreference(key, value).catch(() => {
        // Non-fatal by design: the choice is already applied above. Retrying here would fight
        // the transport's deliberate one-attempt rule for this write (ADR-0032).
      });
    },
    [bridge],
  );

  const setTheme = useCallback(
    (name: string | null) => {
      chosen.current.theme = true;
      setAppearance((current) => ({ ...current, theme: name }));
      // `null` means "follow the system", which the record expresses as a cleared key.
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

  return { appearance, setTheme, setMark };
}
