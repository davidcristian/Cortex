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

  it("maps tokens to CSS custom properties", () => {
    const vars = toCssVars(MIDNIGHT);
    expect(vars["--bg"]).toBe("#0C0A12");
    expect(vars["--bubble-user"]).toBe(MIDNIGHT.tokens.bubbleUser);
    expect(vars["--accent"]).toBe(MIDNIGHT.tokens.accent);
  });

  it("applies a theme's variables and scheme to an element", () => {
    const el = document.createElement("div");
    applyTheme(DAYLIGHT, el);
    expect(el.style.getPropertyValue("--bg")).toBe(DAYLIGHT.tokens.bg);
    expect(el.style.getPropertyValue("--spark")).toBe("#4FE3D0");
    expect(el.dataset.theme).toBe("light");
  });
});
