import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { SessionSummary } from "../bridge/types";
import { NO_OTHER_CHATS } from "../overlay/notice";
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
const list = (
  sessions: readonly SessionSummary[],
  currentId = "c1",
  anchor: { readonly current: HTMLElement | null } = nowhere,
  onDelete: (sessionId: string) => void = vi.fn(),
) => (
  <SessionList
    sessions={sessions}
    currentId={currentId}
    onSelect={vi.fn()}
    onRename={vi.fn()}
    onDelete={onDelete}
    onPin={vi.fn()}
    anchor={anchor}
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

/** The caret's landing place when the list empties, for the tests that are not about it. */
const nowhere = { current: null };

/** A real anchor: the header control the switcher hangs off in production, standing in the page so
 *  the caret has somewhere to go when the list runs out of rows. */
function anchored(): { current: HTMLButtonElement } {
  const button = document.createElement("button");
  button.setAttribute("aria-label", "Recent chats");
  document.body.append(button);
  return { current: button };
}

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
        anchor={nowhere}
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
        anchor={nowhere}
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
        anchor={nowhere}
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
        anchor={nowhere}
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
        anchor={nowhere}
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
        anchor={nowhere}
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
        anchor={nowhere}
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
        anchor={nowhere}
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
        anchor={nowhere}
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

  // WHERE THE CARET GOES FOR THE GESTURES THAT SWAP NOTHING (`overlay/rowCaret.ts`). Every one of
  // these takes the control that fired it off the page, and measured at 900x900 every one of them
  // left `document.activeElement` on `<body>`, outside the panel entirely.
  it("puts the caret in the rename editor, with the name it is replacing selected", () => {
    render(list([summary(), summary({ sessionId: "c2", title: "Second" })]));
    fireEvent.click(screen.getByLabelText("Rename First chat"));
    const input = screen.getByLabelText<HTMLInputElement>("New chat name");
    expect(document.activeElement).toBe(input);
    // Renaming a thing means replacing its name, so typing replaces it and one Backspace is the
    // empty submit that clears a custom title back to the derived one.
    expect([input.selectionStart, input.selectionEnd]).toEqual([0, "First chat".length]);
  });

  it("keeps a cancelling Escape to itself, the overlay dismissing the panel on the same key", () => {
    // Measured at 900x900 before this: Escape cancelled the rename AND reached the window listener
    // that dismisses the panel, so undoing a rename ended the session. Escape closes the innermost
    // thing, and this editor is the innermost thing there is.
    const heard: string[] = [];
    const listener = (event: KeyboardEvent) => heard.push(event.key);
    window.addEventListener("keydown", listener);
    render(list([summary()]));
    fireEvent.click(screen.getByLabelText("Rename First chat"));
    fireEvent.keyDown(screen.getByLabelText("New chat name"), { key: "Escape" });
    expect(heard).toEqual([]);
    // The delete confirm is the row's other overlay and answers the same way, leaving the question
    // closed rather than the panel dismissed with the question still standing under it.
    fireEvent.click(screen.getByLabelText("Delete First chat"));
    fireEvent.keyDown(screen.getByLabelText("Cancel delete"), { key: "Escape" });
    expect(heard).toEqual([]);
    expect(screen.queryByText("Delete this chat?")).not.toBeInTheDocument();
    expect(document.activeElement).toBe(screen.getByLabelText("Delete First chat"));
    // Every other key is the overlay's business as before: the switcher's own Ctrl+K, the cycle
    // keys and Ctrl+N all still reach it from inside a row.
    fireEvent.keyDown(screen.getByLabelText("Rename First chat"), { key: "Escape" });
    expect(heard).toEqual(["Escape"]);
    fireEvent.keyDown(screen.getByLabelText("Delete First chat"), { key: "k", ctrlKey: true });
    expect(heard).toEqual(["Escape", "k"]);
    window.removeEventListener("keydown", listener);
  });

  it("holds a chord in the editor, where the name it would throw away has no undo", () => {
    // Measured at 900x900 before this, standing in "Everything about model swaps" with "a brand new
    // name" typed into a row: Ctrl+N minted a chat and closed the switcher, Ctrl+↑ and Ctrl+↓ each
    // loaded another conversation and closed it, Ctrl+K closed it on its own, and all four left the
    // row reading its old title when the list was reopened (`overlay/fieldKeys.ts`).
    const heard: string[] = [];
    const listener = (event: KeyboardEvent) => heard.push(event.key);
    window.addEventListener("keydown", listener);
    const onRename = vi.fn();
    render(
      <SessionList
        sessions={[summary()]}
        currentId="c1"
        onSelect={vi.fn()}
        onRename={onRename}
        onDelete={vi.fn()}
        onPin={vi.fn()}
        anchor={nowhere}
      />,
    );
    fireEvent.click(screen.getByLabelText("Rename First chat"));
    const input = screen.getByLabelText<HTMLInputElement>("New chat name");
    fireEvent.change(input, { target: { value: "a brand new name" } });
    for (const key of ["n", "k", "ArrowUp", "ArrowDown"]) {
      fireEvent.keyDown(input, { key, ctrlKey: true });
      fireEvent.keyDown(input, { key, metaKey: true });
    }
    expect(heard).toEqual([]);
    // Held, not answered: the editor is where it was, holding what was typed into it, and nothing
    // has been written. Enter and Escape are the two presses that settle it.
    expect(screen.getByLabelText<HTMLInputElement>("New chat name").value).toBe("a brand new name");
    expect(onRename).not.toHaveBeenCalled();
    // Every unmodified key still goes on to the overlay, `?` included: that one is guarded there by
    // element type, so holding it here would duplicate a rule instead of composing with it.
    fireEvent.keyDown(input, { key: "?" });
    expect(heard).toEqual(["?"]);
    window.removeEventListener("keydown", listener);
  });

  it("lets a chord through the delete confirm, which holds no text to lose", () => {
    const heard: string[] = [];
    const listener = (event: KeyboardEvent) => heard.push(event.key);
    window.addEventListener("keydown", listener);
    render(list([summary()]));
    fireEvent.click(screen.getByLabelText("Delete First chat"));
    fireEvent.keyDown(screen.getByLabelText("Cancel delete"), { key: "n", ctrlKey: true });
    // Measured at 900x900: a new chat, the switcher closed, the caret in the composer and nothing
    // deleted. Asking again costs one press, so there is nothing here for the rule to protect.
    expect(heard).toEqual(["n"]);
    expect(screen.getByText("Delete this chat?")).toBeInTheDocument();
    window.removeEventListener("keydown", listener);
  });

  it("gives the caret back to the pencil when an editor closes, whichever way it closed", () => {
    const { rerender } = render(list([summary()]));
    fireEvent.click(screen.getByLabelText("Rename First chat"));
    fireEvent.submit(screen.getByLabelText("New chat name"));
    expect(document.activeElement).toBe(screen.getByLabelText("Rename First chat"));
    // And the same for the way out that writes nothing.
    rerender(list([summary()]));
    fireEvent.click(screen.getByLabelText("Rename First chat"));
    fireEvent.keyDown(screen.getByLabelText("New chat name"), { key: "Escape" });
    expect(document.activeElement).toBe(screen.getByLabelText("Rename First chat"));
  });

  it("opens a delete confirm on its cancel, never on the trash beside it", () => {
    render(list([summary()]));
    fireEvent.click(screen.getByLabelText("Delete First chat"));
    // Measured at 900x900: with the caret on the confirm, one further Enter deletes the chat; here,
    // the same press puts the row back. The confirm exists so one stray press cannot delete.
    expect(document.activeElement).toBe(screen.getByLabelText("Cancel delete"));
    expect(document.activeElement).not.toBe(screen.getByLabelText("Confirm delete First chat"));
    // Cancelling gives it back to the trash that asked, which is where the reader was.
    fireEvent.click(screen.getByLabelText("Cancel delete"));
    expect(document.activeElement).toBe(screen.getByLabelText("Delete First chat"));
  });

  it("moves the caret down to the row that inherits the gap a deleted chat leaves", () => {
    render(list([chat("a"), chat("b"), chat("c")]));
    fireEvent.click(screen.getByLabelText("Delete b"));
    fireEvent.click(screen.getByLabelText("Confirm delete b"));
    // The same control one row down, so deleting several chats is one gesture repeated rather than
    // a walk back into the list between each.
    expect(document.activeElement).toBe(screen.getByLabelText("Delete c"));
  });

  it("moves it up instead when the row that left was the last one", () => {
    render(list([chat("a"), chat("b")]));
    fireEvent.click(screen.getByLabelText("Delete b"));
    fireEvent.click(screen.getByLabelText("Confirm delete b"));
    expect(document.activeElement).toBe(screen.getByLabelText("Delete a"));
  });

  it("hands the caret to the anchor when the last row leaves, the list having none to give", () => {
    const anchor = anchored();
    render(list([chat("a")], "open", anchor));
    fireEvent.click(screen.getByLabelText("Delete a"));
    fireEvent.click(screen.getByLabelText("Confirm delete a"));
    // The switcher is still open in front of the reader, saying it holds nothing; the control that
    // opened it is the one that closes it again.
    expect(document.activeElement).toBe(anchor.current);
  });

  it("says nothing about the caret when the chat deleted is the one on screen", () => {
    // That delete is a SWAP: a fresh chat arrives in its place and takes the caret to the composer
    // with it (`sessionState.deleteSession`). Aiming at a row first would put the caret somewhere
    // the arriving chat pulls it straight back out of.
    const anchor = anchored();
    render(list([chat("a"), chat("b")], "a", anchor));
    fireEvent.click(screen.getByLabelText("Delete a"));
    fireEvent.click(screen.getByLabelText("Confirm delete a"));
    expect(document.activeElement).toBe(document.body);
    expect(document.activeElement).not.toBe(anchor.current);
  });

  it("leaves the pin toggle's own caret alone, its gesture taking no control away", () => {
    // The one row gesture that needs no answer: pinning regroups the list around the row, and the
    // button rides the move. Measured at 900x900, it held focus at every sample through 700ms.
    render(list([summary()]));
    const toggle = screen.getByLabelText("Pin First chat");
    toggle.focus();
    fireEvent.click(toggle);
    expect(document.activeElement).toBe(screen.getByLabelText("Pin First chat"));
  });

  it("puts up the list's empty line in the words the live region borrows for it", () => {
    // The region says the same thing when the last row leaves (`overlay/notice.ts`), so a reader
    // who hears one and then reads the other must not be told two different things about one
    // empty list. Reddens if either side grows its own wording.
    render(list([]));
    expect(document.querySelector(".switcher-empty")?.textContent).toBe(NO_OTHER_CHATS);
  });
});
