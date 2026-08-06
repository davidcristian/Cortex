import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CaptureDot } from "./CaptureDot";

const ASKED = "The assistant asked to look at your screen during this reply";
const READ = "The assistant looked at your screen during this reply";

describe("CaptureDot", () => {
  it("says only that the assistant asked, until an outcome proves more", () => {
    render(<CaptureDot claim="asked" />);
    const dot = screen.getByRole("status");
    // Pinned against the literal: this is a consent surface, and what it says IS the feature.
    // "asked to look" rather than "looked" is the load-bearing part of this rung. It is what a
    // capture the host refused, one whose self-exclusion failed closed, one the body never
    // answered, and a gated one the user declined all leave on screen, so a label claiming the
    // screen was read would be a false statement in every one of them.
    expect(dot).toHaveAttribute("aria-label", ASKED);
    expect(dot).toHaveAttribute("title", ASKED);
    expect(dot.getAttribute("aria-label")).not.toContain("looked at your screen");
    // Ring only: the eye is shut until the dispatch says otherwise.
    expect(dot.className).toBe("capturedot");
  });

  it("says the screen was read once the dispatch settled ok", () => {
    render(<CaptureDot claim="read" />);
    const dot = screen.getByRole("status");
    expect(dot).toHaveAttribute("aria-label", READ);
    expect(dot).toHaveAttribute("title", READ);
    // And it no longer hedges: the seam proved the pixels reached the model.
    expect(dot.getAttribute("aria-label")).not.toContain("asked");
    // The ring opens its eye rather than filling in, which would make it the connection dot's
    // amber twin sitting right beside it.
    expect(dot.className).toBe("capturedot read");
  });

  it("renders nothing on a turn that never asked", () => {
    const { container } = render(<CaptureDot claim={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});
