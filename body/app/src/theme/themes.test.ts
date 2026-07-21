import { describe, expect, it } from "vitest";

import {
  DAYLIGHT,
  MIDNIGHT,
  THEMES,
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

  it("swaps in one frame: transitions off, tokens written, style flushed, transitions back", () => {
    const el = document.createElement("div");
    const flushes: string[] = [];
    // The forced style read is the load-bearing line. Without it the guard goes on and off inside
    // one task, the browser never resolves style in between, and every control crosses the theme at
    // whatever pace its own hover transition uses: measured at 60Hz, the text took the new colour in
    // the frame of the click and the pin, pencil, trash and tab labels took another nine to twenty.
    Object.defineProperty(el, "offsetHeight", {
      configurable: true,
      get: () => {
        flushes.push(el.dataset.swapping === "" ? "guarded" : "unguarded");
        return 0;
      },
    });
    applyTheme(MIDNIGHT, el);
    expect(flushes).toEqual(["guarded"]);
    expect(el.style.getPropertyValue("--bg")).toBe(MIDNIGHT.tokens.bg);
    // And nothing is left holding the overlay's transitions down afterwards.
    expect(el.dataset.swapping).toBeUndefined();
  });
});
