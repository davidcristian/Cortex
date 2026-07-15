import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { DueReminder } from "../bridge/types";
import { Reminders } from "./Reminders";

const NOW = 1_700_000_000_000;

const reminder = (over: Partial<DueReminder> = {}): DueReminder => ({
  reminderId: "r-1",
  text: "Stand-up in 10 minutes",
  firedAtUnixMs: NOW - 5 * 60 * 1000,
  recurring: false,
  tainted: false,
  sessionId: "s1",
  ...over,
});

describe("Reminders", () => {
  afterEach(() => vi.useRealTimers());

  it("shows each reminder's text and how long ago it fired", () => {
    vi.useFakeTimers({ now: NOW });
    render(<Reminders reminders={[reminder(), reminder({ reminderId: "r-2", text: "Stretch" })]} onDismiss={vi.fn()} />);
    expect(screen.getByText("Stand-up in 10 minutes")).toBeTruthy();
    expect(screen.getByText("Stretch")).toBeTruthy();
    expect(screen.getAllByText("5m ago")).toHaveLength(2);
  });

  it("marks a recurring reminder as repeating, so dismissing does not read as cancelling", () => {
    render(<Reminders reminders={[reminder({ recurring: true })]} onDismiss={vi.fn()} />);
    expect(screen.getByText("repeats")).toBeTruthy();
  });

  it("badges untrusted provenance and leaves a plain reminder unbadged", () => {
    const { rerender } = render(<Reminders reminders={[reminder()]} onDismiss={vi.fn()} />);
    expect(screen.queryByText("untrusted source")).toBeNull();
    expect(screen.queryByText("repeats")).toBeNull();
    rerender(<Reminders reminders={[reminder({ tainted: true })]} onDismiss={vi.fn()} />);
    expect(screen.getByText("untrusted source")).toBeTruthy();
  });

  it("renders reminder text as inert text, never as markup or a link", () => {
    // Reminder text is the one string the overlay shows that no output guardrail inspected
    // (ADR-0015 filters replies, not store rows), so nothing in it may become clickable.
    const hostile = '<a href="http://evil.example">click me</a> http://evil.example';
    const { container } = render(<Reminders reminders={[reminder({ text: hostile })]} onDismiss={vi.fn()} />);
    expect(screen.getByText(hostile)).toBeTruthy();
    expect(container.querySelector("a")).toBeNull();
  });

  it("dismissing a card reports that reminder's id", () => {
    const onDismiss = vi.fn();
    render(
      <Reminders
        reminders={[reminder(), reminder({ reminderId: "r-2", text: "Stretch" })]}
        onDismiss={onDismiss}
      />,
    );
    fireEvent.click(screen.getAllByLabelText("Dismiss reminder")[1]!);
    expect(onDismiss).toHaveBeenCalledWith("r-2");
  });
});
