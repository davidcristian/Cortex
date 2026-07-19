import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { WOBBLE } from "../mark/marks";
import { Orb } from "./Orb";

function stubMotionPreference(reduce: boolean): void {
  vi.spyOn(window, "matchMedia").mockReturnValue({
    matches: reduce,
    media: "(prefers-reduced-motion: reduce)",
    onchange: null,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    addListener: () => undefined,
    removeListener: () => undefined,
    dispatchEvent: () => false,
  } as MediaQueryList);
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Orb", () => {
  it("shows the bubble mark, warping on its own clock, and reopens the turn when clicked", () => {
    stubMotionPreference(false);
    const frames = vi.spyOn(window, "requestAnimationFrame");
    const onClick = vi.fn();
    render(<Orb style={WOBBLE} onClick={onClick} />);
    const button = screen.getByLabelText(/Reopen/u);
    expect(button.querySelector("svg.mark")).not.toBeNull();
    expect(frames).toHaveBeenCalled();
    fireEvent.click(button);
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("holds the mark still, scheduling no frames, under prefers-reduced-motion", () => {
    stubMotionPreference(true);
    const frames = vi.spyOn(window, "requestAnimationFrame");
    render(<Orb style={WOBBLE} onClick={vi.fn()} />);
    expect(screen.getByLabelText(/Reopen/u).querySelector("svg.mark")).not.toBeNull();
    expect(frames).not.toHaveBeenCalled();
  });
});
