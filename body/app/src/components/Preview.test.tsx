import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Preview } from "./Preview";

describe("Preview", () => {
  it("shows the reply and opens the panel when clicked", () => {
    const onClick = vi.fn();
    render(<Preview reply="the answer" onClick={onClick} />);
    expect(screen.getByText("the answer")).toBeInTheDocument();
    fireEvent.click(screen.getByText(/Reply ready/u));
    expect(onClick).toHaveBeenCalledOnce();
  });
});
