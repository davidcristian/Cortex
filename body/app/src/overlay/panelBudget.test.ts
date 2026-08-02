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
    // Why this is one function and not two writes at each call site: a panel capped at one height
    // with the sections inside it sized for another is the defect the budget replaced, arriving
    // again by a different route. A placement writes the cap up to three times, and the number the
    // sections are spending has to be the last one every time.
    const element = document.createElement("div");
    capTo(element, 547);
    capTo(element, 351);
    expect(element.style.maxHeight).toBe("351px");
    expect(element.style.getPropertyValue(CEILING_PROPERTY)).toBe("351px");
  });

  it("names the property overlay.css reads, which is the whole of the coupling", () => {
    // The stylesheet's `var(--ceiling, 100vh)` and this constant are the two halves of one seam, and
    // nothing machine-checks that they still agree: Vitest runs with CSS processing off, so the
    // stylesheet's bytes are not readable from inside this toolchain (`overlay.css?raw` resolves to
    // the same empty stub a plain import does, and an assertion against an empty string passes for
    // the wrong reason). Pinning the literal here is what a rename has to walk past, and it is the
    // same arrangement `data-resizing` already has with the rule that hides the history's thumb.
    expect(CEILING_PROPERTY).toBe("--ceiling");
  });
});
