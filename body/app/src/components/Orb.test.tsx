import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Orb } from "./Orb";

describe("Orb", () => {
  it("shows the living rings and reopens the turn when clicked", () => {
    const onClick = vi.fn();
    render(<Orb onClick={onClick} />);
    const button = screen.getByLabelText(/Reopen/u);
    expect(button.querySelectorAll("path.ring")).toHaveLength(2);
    fireEvent.click(button);
    expect(onClick).toHaveBeenCalledOnce();
  });
});
