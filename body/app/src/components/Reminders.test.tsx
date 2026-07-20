import { act, fireEvent, render, screen } from "@testing-library/react";
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

interface Handlers {
  currentId?: string;
  onDismiss?: (reminderId: string) => void;
  onOpen?: (sessionId: string) => void;
}

function renderStack(reminders: readonly DueReminder[], handlers: Handlers = {}) {
  return render(
    <Reminders
      reminders={reminders}
      currentId={handlers.currentId ?? "open-chat"}
      onDismiss={handlers.onDismiss ?? vi.fn()}
      onOpen={handlers.onOpen ?? vi.fn()}
    />,
  );
}

afterEach(() => {
  vi.useRealTimers();
});

/** Let a dismissed card finish rolling shut, which is when its ack is actually sent. Timers are
 *  faked here and not for the file: the cards print how long ago they fired, so a frozen clock
 *  changes what every other test in here is reading. */
const rollShut = () => act(() => vi.advanceTimersByTime(300));

describe("Reminders", () => {
  afterEach(() => vi.useRealTimers());

  it("shows each reminder's text and how long ago it fired", () => {
    vi.useFakeTimers({ now: NOW });
    renderStack([reminder(), reminder({ reminderId: "r-2", text: "Stretch" })]);
    expect(screen.getByText("Stand-up in 10 minutes")).toBeTruthy();
    expect(screen.getByText("Stretch")).toBeTruthy();
    expect(screen.getAllByText("5m ago")).toHaveLength(2);
  });

  it("marks a recurring reminder as repeating, so dismissing does not read as cancelling", () => {
    renderStack([reminder({ recurring: true })]);
    expect(screen.getByText("repeats")).toBeTruthy();
  });

  it("badges untrusted provenance and leaves a plain reminder unbadged", () => {
    const { rerender } = renderStack([reminder()]);
    expect(screen.queryByText("untrusted source")).toBeNull();
    expect(screen.queryByText("repeats")).toBeNull();
    rerender(
      <Reminders
        reminders={[reminder({ tainted: true })]}
        currentId="open-chat"
        onDismiss={vi.fn()}
        onOpen={vi.fn()}
      />,
    );
    expect(screen.getByText("untrusted source")).toBeTruthy();
  });

  it("renders reminder text as inert text, never as markup or a link", () => {
    // Reminder text is the one string the overlay shows that no output guardrail inspected
    // (ADR-0015 filters replies, not store rows), so nothing in it may become clickable.
    const hostile = '<a href="http://evil.example">click me</a> http://evil.example';
    const { container } = renderStack([reminder({ text: hostile })]);
    expect(screen.getByText(hostile)).toBeTruthy();
    expect(container.querySelector("a")).toBeNull();
  });

  it("dismissing a card reports that reminder's id", () => {
    const onDismiss = vi.fn();
    renderStack([reminder(), reminder({ reminderId: "r-2", text: "Stretch" })], { onDismiss });
    vi.useFakeTimers();
    fireEvent.click(screen.getAllByLabelText("Dismiss reminder")[1]!);
    // The card rolls shut first and is handed over only once it has: acking straight away deleted
    // the row in a frame, so the card vanished, the stack closed over the hole, and the panel eased
    // down after both.
    rollShut();
    expect(onDismiss).toHaveBeenCalledWith("r-2");
  });

  it("opens the chat a reminder came from, and never acks it in passing", () => {
    // Acking destroys the reminder and opening does not, so the two gestures stay separate:
    // a mis-click on the way to the context may not silently clear what it came to explain.
    const onOpen = vi.fn();
    const onDismiss = vi.fn();
    renderStack([reminder(), reminder({ reminderId: "r-2", sessionId: "s2" })], {
      onOpen,
      onDismiss,
    });
    fireEvent.click(screen.getAllByText("open chat")[1]!);
    expect(onOpen).toHaveBeenCalledWith("s2");
    expect(onDismiss).not.toHaveBeenCalled();
  });

  it("offers no origin for a session-less reminder or for the chat already on screen", () => {
    renderStack([reminder({ sessionId: "" }), reminder({ reminderId: "r-2", sessionId: "here" })], {
      currentId: "here",
    });
    expect(screen.getAllByLabelText("Dismiss reminder")).toHaveLength(2);
    expect(screen.queryByText("open chat")).toBeNull();
  });
});
