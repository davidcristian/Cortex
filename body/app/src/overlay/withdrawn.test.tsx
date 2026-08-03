import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { withdrawn } from "./withdrawn";

describe("withdrawn", () => {
  it("hides a subtree from assistive tech and from the tab key at once", () => {
    expect(withdrawn(true)).toEqual({ "aria-hidden": true, inert: "" });
  });

  it("says so in both directions for the reader and in one for the tab key", () => {
    const back = withdrawn(false);
    expect(back["aria-hidden"]).toBe(false);
    expect("inert" in back).toBe(false);
  });

  it("reaches the DOM through React 18, which types no `inert` and drops a boolean one", () => {
    const { container, rerender } = render(<div data-testid="pane" {...withdrawn(true)} />);
    const pane = container.firstElementChild as HTMLElement;
    expect(pane.getAttribute("inert")).toBe("");
    expect(pane.getAttribute("aria-hidden")).toBe("true");

    rerender(<div data-testid="pane" {...withdrawn(false)} />);
    expect(pane.hasAttribute("inert")).toBe(false);
    expect(pane.getAttribute("aria-hidden")).toBe("false");
  });
});
