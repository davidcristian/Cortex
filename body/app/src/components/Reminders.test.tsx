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
  anchor?: { readonly current: HTMLElement | null };
  onDismiss?: (reminder: DueReminder) => void;
  onOpen?: (sessionId: string) => void;
}

/** Where the caret goes when the stack empties, for the tests that are not about it. */
const nowhere = { current: null };

/** A real anchor: the composer's field, which is what the reader is left with once the last
 *  reminder is acked and the section is removed with it. */
function anchored(): { current: HTMLTextAreaElement } {
  const composer = document.createElement("textarea");
  composer.setAttribute("aria-label", "Message");
  document.body.append(composer);
  return { current: composer };
}

const stack = (reminders: readonly DueReminder[], handlers: Handlers = {}) => (
  <Reminders
    reminders={reminders}
    currentId={handlers.currentId ?? "open-chat"}
    onDismiss={handlers.onDismiss ?? vi.fn()}
    onOpen={handlers.onOpen ?? vi.fn()}
    anchor={handlers.anchor ?? nowhere}
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
    vi.useFakeTimers({ now: NOW });
    const { container } = renderStack([reminder({ sessionId: "open-chat" })]);
    expect(container.querySelector(".reminder-meta")).toBeNull();
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
        anchor={nowhere}
      />,
    );
    expect(screen.getByText("untrusted source")).toBeTruthy();
  });

  it("renders reminder text as inert text, never as markup or a link", () => {
    const hostile = '<a href="http://evil.example">click me</a> http://evil.example';
    const { container } = renderStack([reminder({ text: hostile })]);
    expect(screen.getByText(hostile)).toBeTruthy();
    expect(container.querySelector("a")).toBeNull();
  });

  it("dismissing a card reports that reminder's id, in the frame the check is pressed", () => {
    const onDismiss = vi.fn();
    const { unmount } = renderStack([reminder(), reminder({ reminderId: "r-2", text: "Stretch" })], {
      onDismiss,
    });
    fireEvent.click(screen.getAllByLabelText("Dismiss reminder")[1]!);
    expect(onDismiss).toHaveBeenCalledWith(
      expect.objectContaining({ reminderId: "r-2", firedAtUnixMs: NOW - 5 * 60 * 1000 }),
    );
    unmount();
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("holds an acked row through its own roll while the rest of the stack keeps its place", () => {
    const land = stubRoll();
    const three = [
      reminder(),
      reminder({ reminderId: "r-2", text: "Stretch" }),
      reminder({ reminderId: "r-3", text: "Drink water" }),
    ];
    const { rerender } = renderStack(three);
    fireEvent.click(screen.getAllByLabelText("Dismiss reminder")[1]!);
    rerender(stack([three[0]!, three[2]!]));
    expect(screen.getAllByLabelText("Dismiss reminder")).toHaveLength(3);
    expect(screen.getByText("Stretch")).toBeTruthy();
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

  it("moves the caret down the stack, so clearing what fired is one key pressed again", () => {
    const three = [
      reminder(),
      reminder({ reminderId: "r-2", text: "Stretch" }),
      reminder({ reminderId: "r-3", text: "Drink water" }),
    ];
    const { rerender } = renderStack(three);
    const acks = () => screen.getAllByLabelText("Dismiss reminder");
    fireEvent.click(acks()[1]!);
    rerender(stack([three[0]!, three[2]!]));
    expect(acks()).toHaveLength(2);
    expect(document.activeElement).toBe(acks()[1]);
    expect(document.activeElement?.closest(".reminder")?.textContent).toContain("Drink water");
  });

  it("takes the last reminder's caret up to the row above it", () => {
    const two = [reminder(), reminder({ reminderId: "r-2", text: "Stretch" })];
    const { rerender } = renderStack(two);
    fireEvent.click(screen.getAllByLabelText("Dismiss reminder")[1]!);
    rerender(stack([two[0]!]));
    expect(document.activeElement?.closest(".reminder")?.textContent).toContain(
      "Stand-up in 10 minutes",
    );
  });

  it("hands the caret to the anchor when the only reminder is acked, the stack going with it", () => {
    const anchor = anchored();
    const { rerender } = renderStack([reminder()], { anchor });
    fireEvent.click(screen.getByLabelText("Dismiss reminder"));
    rerender(stack([], { anchor }));
    expect(document.activeElement).toBe(anchor.current);
  });

  it("withdraws an acked row for its exit, so the tab order cannot walk back into it", () => {
    const land = stubRoll();
    const two = [reminder(), reminder({ reminderId: "r-2", text: "Stretch" })];
    const { rerender } = renderStack(two);
    const slots = () => [...document.querySelectorAll<HTMLElement>(".reminder-slot")];
    expect(slots().map((slot) => slot.hasAttribute("inert"))).toEqual([false, false]);
    fireEvent.click(screen.getAllByLabelText("Dismiss reminder")[1]!);
    rerender(stack([two[0]!]));
    expect(slots()[1]!.hasAttribute("inert")).toBe(true);
    expect(slots()[1]!.getAttribute("aria-hidden")).toBe("true");
    expect(slots()[0]!.hasAttribute("inert")).toBe(false);
    land();
    expect(slots()).toHaveLength(1);
  });
});
