import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { DueReminder } from "../bridge/types";
import { stubRoll } from "../test-setup";
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

const stack = (reminders: readonly DueReminder[], handlers: Handlers = {}) => (
  <Reminders
    reminders={reminders}
    currentId={handlers.currentId ?? "open-chat"}
    onDismiss={handlers.onDismiss ?? vi.fn()}
    onOpen={handlers.onOpen ?? vi.fn()}
  />
);

function renderStack(reminders: readonly DueReminder[], handlers: Handlers = {}) {
  return render(stack(reminders, handlers));
}

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

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

  it("puts the control before the badges, and the timestamp in the side column", () => {
    // The one thing you can DO on the row comes before the badges that only describe it, so it
    // sits at a fixed x down the stack instead of being pushed along by however many badges a
    // given reminder carries. The timestamp is not one of those badges: it is the row's other
    // fact, and it lives in the right column under the dismiss control.
    vi.useFakeTimers({ now: NOW });
    const { container } = renderStack([
      reminder({ recurring: true, tainted: true, sessionId: "s-other" }),
    ]);
    const meta = container.querySelector(".reminder-meta") as HTMLElement;
    expect([...meta.children].map((child) => child.textContent)).toEqual([
      "open chat",
      "repeats",
      "untrusted source",
    ]);
    const side = container.querySelector(".reminder-side") as HTMLElement;
    expect([...side.children].map((child) => child.className)).toEqual([
      "reminder-ack",
      "reminder-time",
    ]);
    expect(side.querySelector(".reminder-time")?.textContent).toBe("5m ago");
  });

  it("drops the meta line entirely when a reminder has nothing to put on it", () => {
    // One-shot, untrusted by nobody, and already in the chat on screen: no control and no
    // badges, so an empty row would only spend its own top margin.
    vi.useFakeTimers({ now: NOW });
    const { container } = renderStack([reminder({ sessionId: "open-chat" })]);
    expect(container.querySelector(".reminder-meta")).toBeNull();
    // The timestamp is unaffected: it never lived on that line.
    expect(container.querySelector(".reminder-time")?.textContent).toBe("5m ago");
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

  it("dismissing a card reports that reminder's id, in the frame the check is pressed", () => {
    // The ack is the user's gesture and the roll is the overlay's answer to it, so the ack does
    // not wait: held behind a timer the roll's length long, it was lost outright whenever the
    // stack was unmounted inside those 300ms (a new chat, or the chat a reminder points at).
    const onDismiss = vi.fn();
    const { unmount } = renderStack([reminder(), reminder({ reminderId: "r-2", text: "Stretch" })], {
      onDismiss,
    });
    fireEvent.click(screen.getAllByLabelText("Dismiss reminder")[1]!);
    expect(onDismiss).toHaveBeenCalledWith("r-2");
    unmount();
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("holds an acked row through its own roll while the rest of the stack keeps its place", () => {
    // The defect: the row was the caller's, so the optimistic ack deleted it in a frame and the
    // rows under it snapped up into the hole. It is held here until its roll ends, and the roll
    // is what closes the gap.
    const land = stubRoll();
    const three = [
      reminder(),
      reminder({ reminderId: "r-2", text: "Stretch" }),
      reminder({ reminderId: "r-3", text: "Drink water" }),
    ];
    const { rerender } = renderStack(three);
    fireEvent.click(screen.getAllByLabelText("Dismiss reminder")[1]!);
    // What the reducer does with that ack, on the spot: the reminder is gone from the list.
    rerender(stack([three[0]!, three[2]!]));
    expect(screen.getAllByLabelText("Dismiss reminder")).toHaveLength(3);
    expect(screen.getByText("Stretch")).toBeTruthy();
    // Between its neighbours, still, rather than shunted to the end of the stack.
    expect([...document.querySelectorAll(".reminder-text")].map((row) => row.textContent)).toEqual([
      "Stand-up in 10 minutes",
      "Stretch",
      "Drink water",
    ]);
    land();
    expect(screen.queryByText("Stretch")).toBeNull();
    expect(screen.getAllByLabelText("Dismiss reminder")).toHaveLength(2);
  });

  it("shows a reminder that returns before its exit ends, rather than holding it shut for good", () => {
    // A lost ack leaves the reminder deliverable and the next summon lists it again under the id
    // it left with (ADR-0025). Held shut, that row would occupy its place in the stack and never
    // be seen again.
    const land = stubRoll();
    const two = [reminder(), reminder({ reminderId: "r-2", text: "Stretch" })];
    const { rerender } = renderStack(two);
    fireEvent.click(screen.getAllByLabelText("Dismiss reminder")[1]!);
    rerender(stack([two[0]!]));
    rerender(stack(two));
    land();
    expect(screen.getByText("Stretch")).toBeTruthy();
    expect(screen.getAllByLabelText("Dismiss reminder")).toHaveLength(2);
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
