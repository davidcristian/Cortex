// The overlay's themes. A theme is a named set of design tokens, and adding one to `THEMES` makes
// it selectable. `accent` and `spark` are used only on controls that are working (thinking,
// streaming, the orb); the status trio `ok`/`warn`/`bad` belongs to the connection indicator.

export type Scheme = "light" | "dark";

/** The tokens every theme provides. */
export interface ThemeTokens {
  readonly bg: string;
  readonly panel: string;
  /** The panel's face behind a liquid edge: the same ground, nearly opaque. Chromium composites
   *  a backdrop blur un-clipped, so a path-clipped panel loses it and opacity stands in. */
  readonly panelSolid: string;
  readonly stroke: string;
  readonly text: string;
  readonly muted: string;
  readonly dim: string;
  readonly bubbleUser: string;
  readonly bubbleAi: string;
  readonly field: string;
  readonly control: string;
  readonly accent: string; // a gradient for activity only (thinking / streaming / orb)
  readonly spark: string; // the "alive" solid accent
  readonly ok: string; // status: the brain is ready
  readonly warn: string; // status: reachable, not serving
  readonly bad: string; // status: unreachable
}

export interface Theme {
  readonly name: string;
  /** How the theme is named on its tile; `name` stays the lowercase storage key. */
  readonly label: string;
  readonly scheme: Scheme;
  readonly tokens: ThemeTokens;
}

const ACTIVITY = {
  accent: "linear-gradient(135deg, #8B5CF6 0%, #E24BC4 52%, #FF7A6B 100%)",
  spark: "#4FE3D0",
} as const;

export const MIDNIGHT: Theme = {
  name: "midnight",
  label: "Midnight",
  scheme: "dark",
  tokens: {
    bg: "#0C0A12",
    panel: "rgba(22, 20, 33, 0.72)",
    panelSolid: "rgba(21, 19, 31, 0.94)",
    stroke: "rgba(255, 255, 255, 0.09)",
    text: "#F2F0F8",
    muted: "#9691AC",
    dim: "#6B6786",
    bubbleUser: "rgba(255, 255, 255, 0.085)",
    bubbleAi: "rgba(255, 255, 255, 0.045)",
    field: "rgba(255, 255, 255, 0.06)",
    control: "rgba(255, 255, 255, 0.05)",
    ok: "#43D675",
    warn: "#FFB347",
    bad: "#FF5F6D",
    ...ACTIVITY,
  },
};

export const DAYLIGHT: Theme = {
  name: "daylight",
  label: "Daylight",
  scheme: "light",
  tokens: {
    bg: "#EFEFF4",
    panel: "rgba(252, 252, 254, 0.74)",
    panelSolid: "rgba(250, 250, 252, 0.95)",
    stroke: "rgba(20, 16, 40, 0.09)",
    text: "#191626",
    muted: "#605D74",
    dim: "#95929F",
    bubbleUser: "rgba(20, 16, 40, 0.055)",
    bubbleAi: "rgba(20, 16, 40, 0.03)",
    field: "rgba(20, 16, 40, 0.04)",
    control: "rgba(20, 16, 40, 0.05)",
    // The same three hues, deepened: the dark theme's values wash out on a light panel.
    ok: "#1EA95C",
    warn: "#C07408",
    bad: "#D93B4A",
    ...ACTIVITY,
  },
};

/** The registry is plug-and-play: add a `Theme` here and it becomes selectable. */
export const THEMES: readonly Theme[] = [MIDNIGHT, DAYLIGHT];

const DEFAULT_DARK = MIDNIGHT;
const DEFAULT_LIGHT = DAYLIGHT;

/** Resolve the active theme: an explicit theme name wins; otherwise follow the system scheme. */
export function resolveTheme(preference: string | null, systemPrefersDark: boolean): Theme {
  if (preference !== null) {
    const chosen = THEMES.find((theme) => theme.name === preference);
    if (chosen !== undefined) {
      return chosen;
    }
  }
  return systemPrefersDark ? DEFAULT_DARK : DEFAULT_LIGHT;
}

/** Map a theme's tokens to the `--token` CSS custom properties the styles consume. */
export function toCssVars(theme: Theme): Record<string, string> {
  const t = theme.tokens;
  return {
    "--bg": t.bg,
    "--panel": t.panel,
    "--panel-solid": t.panelSolid,
    "--stroke": t.stroke,
    "--text": t.text,
    "--muted": t.muted,
    "--dim": t.dim,
    "--bubble-user": t.bubbleUser,
    "--bubble-ai": t.bubbleAi,
    "--field": t.field,
    "--control": t.control,
    "--accent": t.accent,
    "--spark": t.spark,
    "--ok": t.ok,
    "--warn": t.warn,
    "--bad": t.bad,
  };
}

/** How long a theme takes to cross, and the only place the number lives. `applyTheme` writes it
 *  to the root as `--theme-swap`, which `[data-swapping] *` in overlay.css reads. */
export const THEME_SWAP_MS = 400;

/** The swap in flight, so a second toggle inside the first one's window is not ended early by
 *  the first one's timer. */
let crossing: ReturnType<typeof setTimeout> | undefined;

/** Apply a theme: write its CSS custom properties and the scheme dataset. `data-swapping` goes on
 *  before the tokens, because a transition starts from the changed style, and comes off on a timer,
 *  because removing it in the same task would leave nothing to ease. */
export function applyTheme(theme: Theme, root: HTMLElement): void {
  if (root.dataset.theme !== undefined) {
    root.style.setProperty("--theme-swap", `${THEME_SWAP_MS}ms`);
    root.dataset.swapping = "";
    clearTimeout(crossing);
    crossing = setTimeout(() => {
      delete root.dataset.swapping;
    }, THEME_SWAP_MS);
  }
  for (const [name, value] of Object.entries(toCssVars(theme))) {
    root.style.setProperty(name, value);
  }
  root.dataset.theme = theme.scheme;
}
