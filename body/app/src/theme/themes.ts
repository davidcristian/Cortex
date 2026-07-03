// The overlay's plug-and-play theme system (ADR-0011, design/overlay-ux.md). A theme is a named
// set of design tokens; adding one to THEMES makes it selectable (no other code changes). Per the
// design, `accent`/`spark` are the only colorful tokens and are used *only* on working affordances
// (thinking, streaming, the orb); everything else is a chosen neutral, light or dark.

export type Scheme = "light" | "dark";

/** The token contract every theme provides. The whole palette surface lives here. */
export interface ThemeTokens {
  readonly bg: string;
  readonly panel: string;
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
}

export interface Theme {
  readonly name: string;
  readonly scheme: Scheme;
  readonly tokens: ThemeTokens;
}

const ACTIVITY = {
  accent: "linear-gradient(135deg, #8B5CF6 0%, #E24BC4 52%, #FF7A6B 100%)",
  spark: "#4FE3D0",
} as const;

export const MIDNIGHT: Theme = {
  name: "midnight",
  scheme: "dark",
  tokens: {
    bg: "#0C0A12",
    panel: "rgba(22, 20, 33, 0.72)",
    stroke: "rgba(255, 255, 255, 0.09)",
    text: "#F2F0F8",
    muted: "#9691AC",
    dim: "#6B6786",
    bubbleUser: "rgba(255, 255, 255, 0.085)",
    bubbleAi: "rgba(255, 255, 255, 0.045)",
    field: "rgba(255, 255, 255, 0.06)",
    control: "rgba(255, 255, 255, 0.05)",
    ...ACTIVITY,
  },
};

export const DAYLIGHT: Theme = {
  name: "daylight",
  scheme: "light",
  tokens: {
    bg: "#EFEFF4",
    panel: "rgba(252, 252, 254, 0.74)",
    stroke: "rgba(20, 16, 40, 0.09)",
    text: "#191626",
    muted: "#605D74",
    dim: "#95929F",
    bubbleUser: "rgba(20, 16, 40, 0.055)",
    bubbleAi: "rgba(20, 16, 40, 0.03)",
    field: "rgba(20, 16, 40, 0.04)",
    control: "rgba(20, 16, 40, 0.05)",
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
  };
}

/** Apply a theme to an element: write its CSS custom properties + the scheme dataset. */
export function applyTheme(theme: Theme, root: HTMLElement): void {
  for (const [name, value] of Object.entries(toCssVars(theme))) {
    root.style.setProperty(name, value);
  }
  root.dataset.theme = theme.scheme;
}
