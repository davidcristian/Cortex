import { describe, expect, it } from "vitest";

import { CEILING_PROPERTY, capTo } from "./panelBudget";

describe("capTo", () => {
  it("caps the element and publishes the same number for the cascade to spend", () => {
    const element = document.createElement("div");
    capTo(element, 436);
    expect(element.style.maxHeight).toBe("436px");
    expect(element.style.getPropertyValue(CEILING_PROPERTY)).toBe("436px");
  });

  it("moves both together, so a later cap can never leave a stale budget behind it", () => {
    const element = document.createElement("div");
    capTo(element, 547);
    capTo(element, 351);
    expect(element.style.maxHeight).toBe("351px");
    expect(element.style.getPropertyValue(CEILING_PROPERTY)).toBe("351px");
  });

  it("names the property overlay.css reads, which is the whole of the coupling", () => {
    expect(CEILING_PROPERTY).toBe("--ceiling");
  });
});
