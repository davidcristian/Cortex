import { describe, expect, it, vi } from "vitest";

import {
  DAYLIGHT,
  MIDNIGHT,
  THEMES,
  THEME_SWAP_MS,
  applyTheme,
  resolveTheme,
  toCssVars,
} from "./themes";

describe("themes", () => {
  it("resolves an explicit theme name over the system scheme", () => {
    expect(resolveTheme("daylight", true)).toBe(DAYLIGHT);
    expect(resolveTheme("midnight", false)).toBe(MIDNIGHT);
  });

  it("falls back to the system scheme for an unknown name", () => {
    expect(resolveTheme("nope", true)).toBe(MIDNIGHT);
    expect(resolveTheme("nope", false)).toBe(DAYLIGHT);
  });

  it("follows the system scheme when there is no preference", () => {
    expect(resolveTheme(null, true)).toBe(MIDNIGHT);
    expect(resolveTheme(null, false)).toBe(DAYLIGHT);
  });

  it("ships light and dark, each with the shared activity accent", () => {
    const schemes = THEMES.map((t) => t.scheme).sort();
    expect(schemes).toEqual(["dark", "light"]);
    for (const theme of THEMES) {
      expect(theme.tokens.accent).toContain("gradient");
      expect(theme.tokens.spark).toBe("#4FE3D0");
    }
  });

  it("gives every theme its own status trio, since a status must be readable on its ground", () => {
    for (const theme of THEMES) {
      for (const token of [theme.tokens.ok, theme.tokens.warn, theme.tokens.bad]) {
        expect(token).toMatch(/^#[0-9A-F]{6}$/u);
      }
      // Three distinct hues, because the indicator's whole job is telling them apart.
      expect(new Set([theme.tokens.ok, theme.tokens.warn, theme.tokens.bad]).size).toBe(3);
    }
    // Light and dark do not share them: the palette's own values wash out on a light panel.
    expect(DAYLIGHT.tokens.ok).not.toBe(MIDNIGHT.tokens.ok);
  });

  it("maps tokens to CSS custom properties", () => {
    const vars = toCssVars(MIDNIGHT);
    expect(vars["--bg"]).toBe("#0C0A12");
    expect(vars["--panel-solid"]).toBe(MIDNIGHT.tokens.panelSolid);
    expect(vars["--bubble-user"]).toBe(MIDNIGHT.tokens.bubbleUser);
    expect(vars["--accent"]).toBe(MIDNIGHT.tokens.accent);
    expect(vars["--ok"]).toBe(MIDNIGHT.tokens.ok);
    expect(vars["--warn"]).toBe(MIDNIGHT.tokens.warn);
    expect(vars["--bad"]).toBe(MIDNIGHT.tokens.bad);
  });

  it("applies a theme's variables and scheme to an element", () => {
    const el = document.createElement("div");
    applyTheme(DAYLIGHT, el);
    expect(el.style.getPropertyValue("--bg")).toBe(DAYLIGHT.tokens.bg);
    expect(el.style.getPropertyValue("--spark")).toBe("#4FE3D0");
    expect(el.dataset.theme).toBe("light");
  });

  it("crosses the whole surface together, for the length of the crossing and no longer", () => {
    vi.useFakeTimers();
    const el = document.createElement("div");

    // The first application is not a crossing: there is nothing on screen to cross from, and easing
    // the tokens in would be the overlay fading up into its own colours on boot.
    applyTheme(DAYLIGHT, el);
    expect(el.dataset.swapping).toBeUndefined();

    // A change is. One transition goes on everything for the duration, because a theme moves the
    // same colour every control eases for its own hover: left alone they crossed at three different
    // speeds, which reads as the window coming apart and going back together.
    applyTheme(MIDNIGHT, el);
    expect(el.dataset.swapping).toBe("");
    expect(el.style.getPropertyValue("--theme-swap")).toBe(`${THEME_SWAP_MS}ms`);
    expect(el.style.getPropertyValue("--bg")).toBe(MIDNIGHT.tokens.bg);

    // It comes off only once the colours have arrived, or the fade is cut short.
    vi.advanceTimersByTime(THEME_SWAP_MS - 1);
    expect(el.dataset.swapping).toBe("");
    vi.advanceTimersByTime(1);
    expect(el.dataset.swapping).toBeUndefined();

    // A second toggle inside the first one's window keeps its own full crossing: the timer that
    // would have ended it belongs to a swap that is over.
    applyTheme(DAYLIGHT, el);
    vi.advanceTimersByTime(THEME_SWAP_MS - 1);
    applyTheme(MIDNIGHT, el);
    vi.advanceTimersByTime(THEME_SWAP_MS - 1);
    expect(el.dataset.swapping).toBe("");
    vi.advanceTimersByTime(1);
    expect(el.dataset.swapping).toBeUndefined();
    vi.useRealTimers();
  });
});
