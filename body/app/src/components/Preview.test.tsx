import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Preview } from "./Preview";

describe("Preview", () => {
  it("shows only the mark, the reply, and the bar, and opens when clicked", () => {
    const onClick = vi.fn();
    const { container } = render(<Preview reply="the answer" onClick={onClick} />);
    expect(screen.getByText("the answer")).toBeInTheDocument();
    expect(container.querySelector("svg.rings")).not.toBeNull();
    expect(container.textContent).toBe("the answer");
    fireEvent.click(screen.getByLabelText("Open reply"));
    expect(onClick).toHaveBeenCalledOnce();
  });
});
