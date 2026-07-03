import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

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

describe("Orb", () => {
  it("shows the animated living rings and reopens the turn when clicked", () => {
    stubMotionPreference(false);
    const onClick = vi.fn();
    render(<Orb onClick={onClick} />);
    const button = screen.getByLabelText(/Reopen/u);
    expect(button.querySelectorAll("path.ring")).toHaveLength(2);
    expect(button.querySelectorAll("animate")).toHaveLength(2);
    fireEvent.click(button);
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("skips the wave-depth pulse under prefers-reduced-motion", () => {
    stubMotionPreference(true);
    render(<Orb onClick={vi.fn()} />);
    const button = screen.getByLabelText(/Reopen/u);
    expect(button.querySelectorAll("path.ring")).toHaveLength(2);
    expect(button.querySelectorAll("animate")).toHaveLength(0);
  });
});
