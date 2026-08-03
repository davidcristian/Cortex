import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { SessionSummary } from "../bridge/types";
import { stubRoll } from "../test-setup";
import { SessionList } from "./SessionList";

const summary = (over: Partial<SessionSummary> = {}): SessionSummary => ({
  sessionId: "c1",
  title: "First chat",
  preview: "hello there",
  lastActivityUnixMs: Date.now() - 5 * 60_000,
  pinned: false,
  ...over,
});

/** The switcher over a given list, with every write stubbed: the exit cases care about which rows
 *  are on screen and in what order, not about what the row's controls report. */
const list = (sessions: readonly SessionSummary[], currentId = "c1") => (
  <SessionList
    sessions={sessions}
    currentId={currentId}
    onSelect={vi.fn()}
    onRename={vi.fn()}
    onDelete={vi.fn()}
    onPin={vi.fn()}
  />
);

/** The rendered rows, top to bottom, a row on its way out starred. */
const rows = (): string[] =>
  [...document.querySelectorAll<HTMLElement>(".switcher-slot")].map(
    (slot) =>
      `${slot.querySelector(".switcher-title")?.textContent ?? "?"}${
        slot.hasAttribute("inert") ? "*" : ""
      }`,
  );

const chat = (id: string): SessionSummary => summary({ sessionId: id, title: id });

afterEach(() => vi.restoreAllMocks());

describe("SessionList", () => {
  it("renders each chat's title and preview, marks the current, and selects on click", () => {
    const onSelect = vi.fn();
    render(
      <SessionList
        sessions={[summary(), summary({ sessionId: "c2", title: "Second", preview: "world" })]}
        currentId="c2"
        onSelect={onSelect}
        onRename={vi.fn()}
        onDelete={vi.fn()}
        onPin={vi.fn()}
      />,
    );
    expect(screen.getByText("First chat")).toBeInTheDocument();
    expect(screen.getByText("world")).toBeInTheDocument();
    // The current chat's button carries the `current` marker class.
    const current = screen.getByText("Second").closest("button");
    expect(current?.className).toContain("current");
    fireEvent.click(screen.getByText("First chat"));
    expect(onSelect).toHaveBeenCalledWith("c1");
  });

  it("announces a named list of rows, not a listbox, and says which chat is open", () => {
    render(list([summary(), summary({ sessionId: "c2", title: "Second" })], "c2"));
    // The `<ul>` claimed `role="listbox"` while nothing under it was ever an option, and the cost
    // was not only the absent role: a `<li>` inside a listbox is not a listitem, so Chromium
    // announced a listbox with no options and rendered every row as `none`, losing the boundaries
    // a reader counts rows by. It is the named list of rows it behaves like now.
    expect(screen.queryByRole("listbox")).toBeNull();
    const rendered = screen.getByRole("list", { name: "Recent chats" });
    const items = within(rendered).getAllByRole("listitem");
    expect(items).toHaveLength(2);
    // Each row keeps all four of its buttons on their own tab stops. An option is a leaf, so the
    // listbox shape would have had to answer for the pin, the pencil and the trash; this one does
    // not, and nothing here holds a roving `tabIndex` that would take three of the four away.
    for (const item of items) {
      const buttons = within(item).getAllByRole("button");
      expect(buttons).toHaveLength(4);
      for (const button of buttons) {
        expect(button.tabIndex).toBe(0);
      }
    }
    // Which chat is open was a tint and nothing else. `aria-selected` would have needed the role
    // that just came off, so the open row carries `aria-current` and the others deny it.
    expect(screen.getByText("Second").closest("button")).toHaveAttribute("aria-current", "true");
    expect(screen.getByText("First chat").closest("button")).toHaveAttribute(
      "aria-current",
      "false",
    );
  });

  it("shows an empty-state line when there are no chats", () => {
    render(
      <SessionList
        sessions={[]}
        currentId="c1"
        onSelect={vi.fn()}
        onRename={vi.fn()}
        onDelete={vi.fn()}
        onPin={vi.fn()}
      />,
    );
    expect(screen.getByText(/no other chats/iu)).toBeInTheDocument();
  });

  it("opens an inline editor on the pencil, prefilled, and saves the trimmed name", () => {
    const onRename = vi.fn();
    render(
      <SessionList
        sessions={[summary(), summary({ sessionId: "c2", title: "Second" })]}
        currentId="c1"
        onSelect={vi.fn()}
        onRename={onRename}
        onDelete={vi.fn()}
        onPin={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByLabelText("Rename First chat"));
    const input = screen.getByLabelText<HTMLInputElement>("New chat name");
    expect(input.value).toBe("First chat"); // prefilled with the current title
    // The other row stays a normal, selectable item while one is being renamed.
    expect(screen.getByText("Second")).toBeInTheDocument();
    fireEvent.change(input, { target: { value: "  Everything about cats  " } });
    fireEvent.submit(input);
    expect(onRename).toHaveBeenCalledWith("c1", "Everything about cats"); // trimmed
    // The editor closes on save, so the row is a normal item again.
    expect(screen.queryByLabelText("New chat name")).not.toBeInTheDocument();
  });

  it("submits an empty label to clear a custom title back to the derived one", () => {
    const onRename = vi.fn();
    render(
      <SessionList
        sessions={[summary()]}
        currentId="c1"
        onSelect={vi.fn()}
        onRename={onRename}
        onDelete={vi.fn()}
        onPin={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByLabelText("Rename First chat"));
    fireEvent.change(screen.getByLabelText("New chat name"), { target: { value: "   " } });
    fireEvent.click(screen.getByLabelText("Save name"));
    expect(onRename).toHaveBeenCalledWith("c1", ""); // "" is the clear-the-override signal
  });

  it("cancels on Escape without renaming, and ignores other keys", () => {
    const onRename = vi.fn();
    render(
      <SessionList
        sessions={[summary()]}
        currentId="c1"
        onSelect={vi.fn()}
        onRename={onRename}
        onDelete={vi.fn()}
        onPin={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByLabelText("Rename First chat"));
    const input = screen.getByLabelText<HTMLInputElement>("New chat name");
    fireEvent.keyDown(input, { key: "a" }); // a non-Escape key leaves the editor open
    expect(screen.getByLabelText("New chat name")).toBeInTheDocument();
    fireEvent.keyDown(input, { key: "Escape" });
    expect(screen.queryByLabelText("New chat name")).not.toBeInTheDocument();
    expect(onRename).not.toHaveBeenCalled();
  });

  it("deletes only after a per-row confirm, so a single trash click never deletes", () => {
    const onDelete = vi.fn();
    render(
      <SessionList
        sessions={[summary(), summary({ sessionId: "c2", title: "Second" })]}
        currentId="c1"
        onSelect={vi.fn()}
        onRename={vi.fn()}
        onDelete={onDelete}
        onPin={vi.fn()}
      />,
    );
    // One click on the trash asks, but does not delete: the confirm replaces the row.
    fireEvent.click(screen.getByLabelText("Delete First chat"));
    expect(onDelete).not.toHaveBeenCalled();
    expect(screen.getByText("Delete this chat?")).toBeInTheDocument();
    // The other row stays a normal, selectable item while one is confirming.
    expect(screen.getByText("Second")).toBeInTheDocument();
    // Confirming fires the destructive write and closes the confirm.
    fireEvent.click(screen.getByLabelText("Confirm delete First chat"));
    expect(onDelete).toHaveBeenCalledWith("c1");
    expect(screen.queryByText("Delete this chat?")).not.toBeInTheDocument();
  });

  it("cancels the delete confirm without deleting", () => {
    const onDelete = vi.fn();
    render(
      <SessionList
        sessions={[summary()]}
        currentId="c1"
        onSelect={vi.fn()}
        onRename={vi.fn()}
        onDelete={onDelete}
        onPin={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByLabelText("Delete First chat"));
    fireEvent.click(screen.getByLabelText("Cancel delete"));
    expect(onDelete).not.toHaveBeenCalled();
    expect(screen.queryByText("Delete this chat?")).not.toBeInTheDocument();
    // Back to a normal row: the trash is offered again.
    expect(screen.getByLabelText("Delete First chat")).toBeInTheDocument();
  });

  it("pins an unpinned chat: the toggle offers 'Pin' and fires onPin(true)", () => {
    const onPin = vi.fn();
    render(
      <SessionList
        sessions={[summary()]}
        currentId="c1"
        onSelect={vi.fn()}
        onRename={vi.fn()}
        onDelete={vi.fn()}
        onPin={onPin}
      />,
    );
    const toggle = screen.getByLabelText("Pin First chat");
    expect(toggle).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(toggle);
    expect(onPin).toHaveBeenCalledWith("c1", true); // pins the target chat
  });

  it("unpins a pinned chat: its row is grouped/marked and the toggle fires onPin(false)", () => {
    const onPin = vi.fn();
    render(
      <SessionList
        sessions={[
          summary({ sessionId: "p1", title: "Pinned", pinned: true }),
          summary({ sessionId: "r1", title: "Recent" }),
        ]}
        currentId="r1"
        onSelect={vi.fn()}
        onRename={vi.fn()}
        onDelete={vi.fn()}
        onPin={onPin}
      />,
    );
    // The pinned row carries the pinned marker class and its toggle reads pressed + offers "Unpin".
    // The marker is on `.switcher-row`, inside the roll, not on the `<li>` slot around it.
    const pinnedRow = screen.getByText("Pinned").closest(".switcher-row");
    expect(pinnedRow?.className).toContain("pinned");
    const toggle = screen.getByLabelText("Unpin Pinned");
    expect(toggle).toHaveAttribute("aria-pressed", "true");
    // The unpinned row does not carry the pinned marker.
    expect(screen.getByText("Recent").closest(".switcher-row")?.className).not.toContain("pinned");
    fireEvent.click(toggle);
    expect(onPin).toHaveBeenCalledWith("p1", false); // unpins the target chat
  });

  it("holds a deleted row through its own roll while its neighbours close over it", () => {
    // The defect: the row was rendered from `sessions`, so a landed delete removed it in a frame
    // and every row under it snapped up 50px into the hole. Held here until its roll ends, and the
    // roll is what closes the gap.
    const land = stubRoll();
    const { rerender } = render(list([chat("a"), chat("b"), chat("c")]));
    rerender(list([chat("a"), chat("c")]));
    expect(rows()).toEqual(["a", "b*", "c"]);
    land();
    expect(rows()).toEqual(["a", "c"]);
  });

  it("withdraws a leaving row, so a deleted chat cannot be opened or deleted again mid-roll", () => {
    // Holding a row on screen for 300ms after its chat is gone is 300ms in which its title still
    // opens a deleted chat and its trash still asks to delete one. The slot is `inert` and
    // `aria-hidden` for the length of the exit, which takes all four buttons out of the pointer's
    // reach and out of the tab order at once.
    const land = stubRoll();
    const { rerender } = render(list([chat("a"), chat("b")]));
    const slots = () => [...document.querySelectorAll<HTMLElement>(".switcher-slot")];
    expect(slots().map((slot) => slot.getAttribute("aria-hidden"))).toEqual(["false", "false"]);
    rerender(list([chat("a")]));
    const leaving = slots()[1]!;
    expect(leaving.getAttribute("aria-hidden")).toBe("true");
    expect(leaving.hasAttribute("inert")).toBe(true);
    // The surviving row is untouched: withdrawal is per row, not per list.
    expect(slots()[0]!.hasAttribute("inert")).toBe(false);
    land();
    expect(slots()).toHaveLength(1);
  });

  it("carries a leaving row with the neighbour it left under when the list reorders", () => {
    // The switcher re-lists after every write, pinned chats first and then by recency, so a pin, a
    // finished turn or a plain refresh can reorder it while a row is still rolling out. The
    // reminder stack never reorders, so this is the case its exit never had to answer. Placed at
    // the index it held, the leaving row lands wherever that ordinal now points, which is a pair of
    // neighbours it was never between; it goes back under its own former neighbour instead.
    const land = stubRoll();
    const { rerender } = render(list([chat("a"), chat("b"), chat("c"), chat("d")]));
    rerender(list([chat("a"), chat("b"), chat("d")])); // c deleted, from under b
    expect(rows()).toEqual(["a", "b", "c*", "d"]);
    rerender(list([chat("d"), chat("a"), chat("b")])); // d pinned: the list re-groups mid-roll
    expect(rows()).toEqual(["d", "a", "b", "c*"]);
    land();
    expect(rows()).toEqual(["d", "a", "b"]);
  });

  it("rolls out every row a whole re-listing dropped, above the ones it brought", () => {
    // Not a delete: the switcher re-lists on every summon and after every write, so a listing that
    // no longer holds any of the chats on screen (another client cleared them, the recency window
    // moved on) is a departure of all of them at once. Each leaves through its own roll, keeping
    // the order it had, and the arrivals take their places underneath.
    const land = stubRoll();
    const { rerender } = render(list([chat("a"), chat("b"), chat("c")]));
    rerender(list([chat("x"), chat("y")]));
    expect(rows()).toEqual(["a*", "b*", "c*", "x", "y"]);
    land();
    expect(rows()).toEqual(["x", "y"]);
  });

  it("holds two deletes at once, each on its own clock", () => {
    const land = stubRoll();
    const { rerender } = render(list([chat("a"), chat("b"), chat("c")]));
    rerender(list([chat("a"), chat("c")]));
    rerender(list([chat("a")]));
    expect(rows()).toEqual(["a", "b*", "c*"]);
    land();
    expect(rows()).toEqual(["a"]);
  });

  it("puts back a row that returns before its exit ends, rather than holding it shut", () => {
    // A failed delete leaves the chat where it was and the next refresh lists it again under the id
    // it left with. Held shut, that row would keep its place in the switcher and never be seen.
    const land = stubRoll();
    const { rerender } = render(list([chat("a"), chat("b")]));
    rerender(list([chat("a")]));
    rerender(list([chat("a"), chat("b")]));
    land();
    expect(rows()).toEqual(["a", "b"]);
  });

  it("survives being unmounted mid-exit, the switcher rolling shut being one way it happens", () => {
    // Selecting a chat closes the switcher, and the section's own roll unmounts the list under any
    // row still leaving inside it. The roll that outlives it still reports back, so what is asserted
    // is that the late `released` lands on nothing: no throw and no React complaint, which is the
    // whole benefit of the hold owning no timer to cancel and no removal to catch up on.
    const complaints = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const land = stubRoll();
    const { rerender, unmount } = render(list([chat("a"), chat("b")]));
    rerender(list([chat("a")]));
    unmount();
    expect(() => land()).not.toThrow();
    expect(complaints).not.toHaveBeenCalled();
    expect(document.querySelectorAll(".switcher-slot")).toHaveLength(0);
  });

  it("grows the empty line into the gap the last row leaves, on that row's own clock", () => {
    // The line used to wait for the roll to end and then arrive in the frame after it, which took
    // the card 14 to 53 in one frame at 900x900 with the panel wobbling after it. It goes up as the
    // row starts leaving instead, and rolls from nothing over the same 300ms, so the card eases
    // from a row's height to a line's and the panel never moves at all.
    const land = stubRoll();
    const { rerender } = render(list([chat("a")]));
    rerender(list([]));
    expect(rows()).toEqual(["a*"]);
    const line = screen.getByText(/no other chats/iu).closest(".collapse");
    expect(line).toHaveAttribute("data-morphing"); // rolling, and the panel can read where to
    land();
    expect(rows()).toEqual([]);
    expect(screen.getByText(/no other chats/iu)).toBeInTheDocument();
    expect(line).not.toHaveAttribute("data-morphing");
  });

  it("yields the empty line in the frame a chat arrives, rather than rolling it out under one", () => {
    // The other direction is not the same flag run backwards. A row lands at its full height at
    // once, so a line rolling away underneath it would grow the card by the row and only then take
    // the line off it, an overshoot bigger than the step it removes. The line is what the list says
    // when it has nothing to say: it waits for the row it replaces and yields to the row that
    // replaces it.
    const land = stubRoll();
    const { rerender } = render(list([]));
    expect(screen.getByText(/no other chats/iu)).toBeInTheDocument();
    rerender(list([chat("a")]));
    expect(screen.queryByText(/no other chats/iu)).toBeNull();
    expect(rows()).toEqual(["a"]);
    land();
    expect(screen.queryByText(/no other chats/iu)).toBeNull();
  });

  it("does not roll the line in when the switcher opens on a list that is already empty", () => {
    // Mounting is not arriving. The list opens inside the switcher's own roll, and a line rolling
    // in underneath that roll would have the section measure itself against a card growing out of
    // nothing.
    stubRoll();
    render(list([]));
    expect(screen.getByText(/no other chats/iu).closest(".collapse")).not.toHaveAttribute(
      "data-morphing",
    );
  });

  it("travels every row a regrouping moved, instead of leaving them at their new places", () => {
    // The switcher re-lists pinned chats first and then by recency, so a pin moves rows that are
    // staying. Traced at 900x900 before this, pinning the third of three chats took it 270 to 170
    // and pushed the two above it 50px each, all inside the frame the re-listing committed.
    const places = new Map([
      ["a", 0],
      ["b", 50],
    ]);
    vi.spyOn(HTMLElement.prototype, "offsetTop", "get").mockImplementation(function (
      this: HTMLElement,
    ) {
      return places.get(this.querySelector(".switcher-title")?.textContent ?? "") ?? 0;
    });
    const played: string[] = [];
    Element.prototype.animate = function (this: Element, keyframes: Keyframe[]) {
      played.push(
        `${String(this.querySelector(".switcher-title")?.textContent)}:${String(
          keyframes[0]?.transform,
        )}`,
      );
      return { cancel: () => undefined } as unknown as Animation;
    } as typeof Element.prototype.animate;
    const { rerender } = render(list([chat("a"), chat("b")]));
    expect(played).toEqual([]);
    places.set("b", 0);
    places.set("a", 50);
    rerender(list([chat("b"), chat("a")]));
    // Each row is handed back the distance it moved, which decays to nothing over the roll's clock.
    expect(played).toEqual(["b:translateY(50px)", "a:translateY(-50px)"]);
  });
});
