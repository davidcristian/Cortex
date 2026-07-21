// The overlay's plug-and-play theme system (ADR-0011, design/overlay-ux.md). A theme is a named
// set of design tokens; adding one to THEMES makes it selectable (no other code changes). Per the
// design, `accent`/`spark` are the colorful tokens of *activity* and are used only on working
// affordances (thinking, streaming, the orb). The status trio (`ok`/`warn`/`bad`) is the one
// other sanctioned use of colour: the connection indicator, where green/amber/red is the
// meaning itself rather than decoration. Everything else is a chosen neutral, light or dark.

export type Scheme = "light" | "dark";

/** The token contract every theme provides. The whole palette surface lives here. */
export interface ThemeTokens {
  readonly bg: string;
  readonly panel: string;
  /** The panel's face when a liquid edge carries it (ADR-0036): the same ground, nearly opaque,
   *  because a path-clipped panel cannot keep its backdrop blur (Chromium composites the blur
   *  un-clipped) and a hair more opacity is the honest trade. */
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
    panelSolid: "rgba(21, 19, 31, 0.94)",
    stroke: "rgba(255, 255, 255, 0.09)",
    text: "#F2F0F8",
    muted: "#9691AC",
    dim: "#6B6786",
    bubbleUser: "rgba(255, 255, 255, 0.085)",
    bubbleAi: "rgba(255, 255, 255, 0.045)",
    field: "rgba(255, 255, 255, 0.06)",
    control: "rgba(255, 255, 255, 0.05)",
    // The status trio is drawn from the user's own eight-hue palette (the rings' gradient
    // stops), so the indicator belongs to the design language instead of importing a
    // traffic-light green from nowhere.
    ok: "#43D675",
    warn: "#FFB347",
    bad: "#FF5F6D",
    ...ACTIVITY,
  },
};

export const DAYLIGHT: Theme = {
  name: "daylight",
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
    // The same three hues, deepened: the palette's own values are tuned for a dark ground and
    // wash out on a light panel, and a status colour that cannot be read is not a status.
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

/** How long a theme takes to cross, and the only place the number lives: `applyTheme` writes it to
 *  the root as `--theme-swap`, and `[data-swapping] *` in overlay.css is what reads it. A duration
 *  declared in the stylesheet as well would be two numbers that have to agree, and the one holding
 *  the attribute on has to outlast the one easing the colours or the fade is cut off mid-way. */
export const THEME_SWAP_MS = 400;

/** The swap in flight, so a second toggle inside the first one's window does not have the first
 *  one's timer end its fade early. */
let crossing: ReturnType<typeof setTimeout> | undefined;

/**
 * Apply a theme to an element: write its CSS custom properties + the scheme dataset.
 *
 * The whole surface CROSSES TOGETHER, which takes one step more than writing the tokens. A theme
 * moves the same `color` that every control eases for its own hover, so left alone each of them
 * crossed at its own pace: measured at 60Hz with the session list up, the titles and previews took
 * the new value in the frame of the click, the pin, the pencil, the trash and the tab labels spent
 * another nine to twenty frames arriving, and the chat's title and the reminder lines, the only text
 * in the panel that inherits the ground's colour rather than setting its own, followed a 0.4s ease
 * on the ground itself. One swap at three speeds reads as the window coming apart and going back
 * together.
 *
 * So `data-swapping` puts ONE transition on everything for the length of the crossing, which is
 * what makes it a crossing rather than each element's own idea of one. It goes on before the tokens
 * so the rule is in the after-change style, which is the style a transition is started from, and it
 * comes off on a timer rather than a style flush: taken off in the same task, there is nothing left
 * to ease and the swap is instant.
 *
 * The FIRST application is not a crossing. Nothing is on screen to cross from, and the tokens
 * arriving over 400ms would be the overlay fading up into its own colours on boot.
 */
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
