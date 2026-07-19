import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CaptureDot } from "./CaptureDot";

const LABEL = "The assistant asked to look at your screen during this reply";

describe("CaptureDot", () => {
  it("says only what the seam proved, in a label a screen reader can announce", () => {
    render(<CaptureDot capturing />);
    const dot = screen.getByRole("status");
    expect(dot).toHaveAttribute("aria-label", LABEL);
    expect(dot).toHaveAttribute("title", LABEL);
    expect(dot.getAttribute("aria-label")).not.toContain("looked at your screen");
  });

  it("renders nothing on a turn that never asked", () => {
    const { container } = render(<CaptureDot capturing={false} />);
    expect(container).toBeEmptyDOMElement();
  });
});
