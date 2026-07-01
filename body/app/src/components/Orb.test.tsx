import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Orb } from "./Orb";

describe("Orb", () => {
  it("reopens the turn when clicked", () => {
    const onClick = vi.fn();
    render(<Orb onClick={onClick} />);
    fireEvent.click(screen.getByLabelText(/Reopen/u));
    expect(onClick).toHaveBeenCalledOnce();
  });
});
