import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { INITIAL_LINK, type LinkView } from "../overlay/linkState";
import { LinkDot } from "./LinkDot";

const view = (over: Partial<LinkView> = {}): LinkView => ({ ...INITIAL_LINK, ...over });

describe("LinkDot", () => {
  it("carries the colour of what the seam last proved", () => {
    const cases: [LinkView, string][] = [
      [view({ state: "ready" }), "ok"],
      [view({ state: "degraded" }), "warn"],
      [view({ state: "down" }), "bad"],
      [view(), "idle"],
    ];
    for (const [link, tone] of cases) {
      const { unmount } = render(<LinkDot link={link} />);
      expect(screen.getByRole("status").className).toBe(`linkdot ${tone}`);
      unmount();
    }
  });

  it("pulses while a probe is out, keeping the last known colour", () => {
    render(<LinkDot link={view({ state: "down", detail: "refused", probing: true })} />);
    expect(screen.getByRole("status").className).toBe("linkdot bad busy");
  });

  it("says what it means, for a pointer and for a screen reader alike", () => {
    // A colour on its own explains nothing, and this dot replaces one that was always green.
    render(<LinkDot link={view({ state: "down", detail: "connection refused" })} />);
    const dot = screen.getByRole("status");
    expect(dot).toHaveAttribute("title", "Cannot reach the brain: connection refused");
    expect(dot).toHaveAccessibleName("Cannot reach the brain: connection refused");
  });
});
