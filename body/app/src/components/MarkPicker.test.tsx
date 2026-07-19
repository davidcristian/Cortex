import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { MARKS, PING, WOBBLE } from "../mark/marks";
import { MarkPicker } from "./MarkPicker";

describe("MarkPicker", () => {
  it("shows the current mark and nothing else until it is asked", () => {
    render(<MarkPicker style={WOBBLE} animated={false} onPick={vi.fn()} />);
    const button = screen.getByLabelText(/Mark: Wobble/u);
    expect(button).toHaveAttribute("aria-expanded", "false");
    expect(button.querySelector("svg.mark")).not.toBeNull();
    expect(screen.queryByRole("radiogroup")).toBeNull();
  });

  it("opens every style, drawn live, with the current one marked", () => {
    render(<MarkPicker style={PING} animated={false} onPick={vi.fn()} />);
    fireEvent.click(screen.getByLabelText(/Mark: Ping/u));
    const options = screen.getAllByRole("radio");
    expect(options).toHaveLength(MARKS.length);
    for (const option of options) {
      expect(option.querySelector("svg.mark")).not.toBeNull();
    }
    expect(screen.getByRole("radio", { name: /Ping/u })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByRole("radio", { name: /Foam/u })).toHaveAttribute("aria-checked", "false");
  });

  it("applies the style that is chosen and closes itself", () => {
    const onPick = vi.fn();
    render(<MarkPicker style={WOBBLE} animated={false} onPick={onPick} />);
    fireEvent.click(screen.getByLabelText(/Mark: Wobble/u));
    fireEvent.click(screen.getByRole("radio", { name: /Foam/u }));
    expect(onPick).toHaveBeenCalledWith("foam");
    expect(screen.queryByRole("radiogroup")).toBeNull();
  });

  it("closes again when the mark is clicked a second time", () => {
    render(<MarkPicker style={WOBBLE} animated={false} onPick={vi.fn()} />);
    const button = screen.getByLabelText(/Mark: Wobble/u);
    fireEvent.click(button);
    expect(screen.getByRole("radiogroup")).toBeInTheDocument();
    fireEvent.click(button);
    expect(screen.queryByRole("radiogroup")).toBeNull();
  });
});
