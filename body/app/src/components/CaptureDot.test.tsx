import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CaptureDot } from "./CaptureDot";

const ASKED = "The assistant asked to look at your screen during this reply";
const READ = "The assistant looked at your screen during this reply";

describe("CaptureDot", () => {
  it("says only that the assistant asked, until an outcome proves more", () => {
    render(<CaptureDot claim="asked" />);
    const dot = screen.getByRole("status");
    // Asserted against the exact string, because this is a consent surface and its wording is what
    // it delivers. "asked to look" rather than "looked" is the whole of this level's claim: a
    // capture the host refused, one whose self-exclusion failed closed, one the body never answered,
    // and a gated one the user declined all leave this label on screen, so a label claiming the
    // screen was read would be false in every one of them.
    expect(dot).toHaveAttribute("aria-label", ASKED);
    expect(dot).toHaveAttribute("title", ASKED);
    expect(dot.getAttribute("aria-label")).not.toContain("looked at your screen");
    // The ring alone, with no centre, until the dispatch reports an outcome.
    expect(dot.className).toBe("capturedot");
  });

  it("says the screen was read once the dispatch settled ok", () => {
    render(<CaptureDot claim="read" />);
    const dot = screen.getByRole("status");
    expect(dot).toHaveAttribute("aria-label", READ);
    expect(dot).toHaveAttribute("title", READ);
    // The claim is now unqualified, because the seam reported that the capture reached the model.
    expect(dot.getAttribute("aria-label")).not.toContain("asked");
    // The ring gains a centre rather than filling in solid, which would make it look like a second
    // connection dot beside the real one.
    expect(dot.className).toBe("capturedot read");
  });

  it("renders nothing on a turn that never asked", () => {
    const { container } = render(<CaptureDot claim={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});
