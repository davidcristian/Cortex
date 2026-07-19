import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CaptureDot } from "./CaptureDot";

const LABEL = "The assistant asked to look at your screen during this reply";

describe("CaptureDot", () => {
  it("says only what the seam proved, in a label a screen reader can announce", () => {
    render(<CaptureDot capturing />);
    const dot = screen.getByRole("status");
    // Pinned against the literal: this is a consent surface, and what it says IS the feature.
    // "asked to look" rather than "looked" is the load-bearing part. The flag behind it is set
    // from the pre-dispatch tool chip, so it is lit even when the host refused the capture, the
    // body was unreachable, or a gated capture was declined; none of those outcomes crosses the
    // seam. A label claiming the screen was read would be a false statement in all of them.
    expect(dot).toHaveAttribute("aria-label", LABEL);
    expect(dot).toHaveAttribute("title", LABEL);
    expect(dot.getAttribute("aria-label")).not.toContain("looked at your screen");
  });

  it("renders nothing on a turn that never asked", () => {
    const { container } = render(<CaptureDot capturing={false} />);
    expect(container).toBeEmptyDOMElement();
  });
});
