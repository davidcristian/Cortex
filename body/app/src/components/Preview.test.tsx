import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Preview } from "./Preview";

describe("Preview", () => {
  it("shows only the reply and the bar, and opens when clicked", () => {
    const onClick = vi.fn();
    const { container } = render(<Preview reply="the answer" onClick={onClick} onHover={vi.fn()} />);
    expect(screen.getByText("the answer")).toBeInTheDocument();
    expect(container.textContent).toBe("the answer");
    fireEvent.click(screen.getByLabelText("Open reply"));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("always wears the Lucid edge, whatever the window registry is set to", () => {
    const { container } = render(<Preview reply="r" onClick={vi.fn()} onHover={vi.fn()} />);
    const edge = container.querySelector(".edge");
    expect(edge).toHaveAttribute("aria-hidden", "true");
    expect(edge?.className).toBe("edge edge-none");
    expect(container.querySelector(".edge-glass")).not.toBeNull();
    expect(container.querySelector(".edge-under")).toBeNull();
  });

  it("reports hover both ways and restarts the drain bar on leave", () => {
    const onHover = vi.fn();
    const { container } = render(<Preview reply="r" onClick={vi.fn()} onHover={onHover} />);
    const card = screen.getByLabelText("Open reply");
    const barBefore = container.querySelector(".bar");
    fireEvent.mouseEnter(card);
    expect(onHover).toHaveBeenLastCalledWith(true);
    fireEvent.mouseLeave(card);
    expect(onHover).toHaveBeenLastCalledWith(false);
    const barAfter = container.querySelector(".bar");
    expect(barAfter).not.toBeNull();
    expect(barAfter).not.toBe(barBefore);
  });
});
