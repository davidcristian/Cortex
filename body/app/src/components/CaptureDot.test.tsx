import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CaptureDot } from "./CaptureDot";

const LABEL = "The assistant looked at your screen during this reply";

describe("CaptureDot", () => {
  it("says plainly that the screen was read, in a label a screen reader can announce", () => {
    render(<CaptureDot capturing />);
    const dot = screen.getByRole("status");
    // Pinned against the literal: this is a consent surface, and what it says IS the feature.
    expect(dot).toHaveAttribute("aria-label", LABEL);
    expect(dot).toHaveAttribute("title", LABEL);
  });

  it("renders nothing on a turn that never looked", () => {
    const { container } = render(<CaptureDot capturing={false} />);
    expect(container).toBeEmptyDOMElement();
  });
});
