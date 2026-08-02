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
    // `inert` is boolean in the HTML sense, so its absence is its false and `inert="false"` would
    // be an inert element. The key has to be gone, not present and empty.
    expect("inert" in back).toBe(false);
  });

  it("reaches the DOM through React 18, which types no `inert` and drops a boolean one", () => {
    // The claim the refinement got wrong, pinned against the tree's own react-dom rather than
    // against its version number: the attribute lands, and it lands from a string.
    const { container, rerender } = render(<div data-testid="pane" {...withdrawn(true)} />);
    const pane = container.firstElementChild as HTMLElement;
    expect(pane.getAttribute("inert")).toBe("");
    expect(pane.getAttribute("aria-hidden")).toBe("true");

    // And it comes off again, which is the half a one-way attribute would fail: a pane arriving
    // has to be reachable in the same frame it stops being the pane that left.
    rerender(<div data-testid="pane" {...withdrawn(false)} />);
    expect(pane.hasAttribute("inert")).toBe(false);
    expect(pane.getAttribute("aria-hidden")).toBe("false");
  });
});
