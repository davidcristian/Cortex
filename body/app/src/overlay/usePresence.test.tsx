import { act, renderHook } from "@testing-library/react";
import { StrictMode } from "react";
import { describe, expect, it } from "vitest";

import { usePresence } from "./usePresence";

interface Row {
  readonly id: string;
  readonly label: string;
}

const row = (id: string, label = id): Row => ({ id, label });
const keyOf = (item: Row): string => item.id;

// Every case here renders under `StrictMode`, because the overlay does (`main.tsx`) and because
// this hook's first shape passed all of these without it and dropped the row on the first frame in
// a real browser. StrictMode invokes a render twice, so a hook that remembers what it just
// rendered by writing a ref during the render reads its own first pass back on the second and
// concludes that nothing has left. The memory is written from a layout effect for that reason,
// and this wrapper is what keeps it that way.

/** The rendered list as one string per row, a leaving row starred: the whole of what this hook
 *  decides is which rows are there, in what order, and which of them are on their way out. */
function shape(entries: readonly { key: string; leaving: boolean }[]): string[] {
  return entries.map((entry) => `${entry.key}${entry.leaving ? "*" : ""}`);
}

describe("usePresence", () => {
  it("hands an untouched list straight back, in order and with the caller's own items", () => {
    const items = [row("a"), row("b")];
    const { result } = renderHook(() => usePresence(items, keyOf), { wrapper: StrictMode });
    expect(shape(result.current.entries)).toEqual(["a", "b"]);
    expect(result.current.entries.map((entry) => entry.item)).toEqual(items);
  });

  it("keeps a removed row where it was, so its neighbours close over it instead of snapping", () => {
    const { result, rerender } = renderHook(({ items }) => usePresence(items, keyOf), {
      wrapper: StrictMode,
      initialProps: { items: [row("a"), row("b", "middle"), row("c")] },
    });
    rerender({ items: [row("a"), row("c")] });
    expect(shape(result.current.entries)).toEqual(["a", "b*", "c"]);
    // Carrying the last version of itself that was on screen: the caller's list no longer has it,
    // so there is nowhere else for the row's own text to come from while it rolls.
    expect(result.current.entries[1]?.item.label).toBe("middle");
  });

  it("drops the row when its exit reports back, and not before", () => {
    const { result, rerender } = renderHook(({ items }) => usePresence(items, keyOf), {
      wrapper: StrictMode,
      initialProps: { items: [row("a"), row("b")] },
    });
    rerender({ items: [row("a")] });
    expect(shape(result.current.entries)).toEqual(["a", "b*"]);
    act(() => result.current.released("b"));
    expect(shape(result.current.entries)).toEqual(["a"]);
  });

  it("holds two exits at once and lets them end in either order", () => {
    // Acking one reminder and then a second before the first has finished leaving. Each row is on
    // its own clock, so the second must not inherit the first's, and releasing the later one first
    // must not take the earlier one with it.
    const { result, rerender } = renderHook(({ items }) => usePresence(items, keyOf), {
      wrapper: StrictMode,
      initialProps: { items: [row("a"), row("b"), row("c")] },
    });
    rerender({ items: [row("a"), row("c")] });
    rerender({ items: [row("a")] });
    expect(shape(result.current.entries)).toEqual(["a", "b*", "c*"]);
    act(() => result.current.released("c"));
    // `b` remembered index 1 of a three-row list and there is one row left, so its place is the
    // end: a row released out of order takes its slot with it rather than leaving a hole.
    expect(shape(result.current.entries)).toEqual(["a", "b*"]);
    act(() => result.current.released("b"));
    expect(shape(result.current.entries)).toEqual(["a"]);
  });

  it("falls back to the remembered index when the row a leaving row hung from is released first", () => {
    // The anchor a leaving row goes back under can itself be a leaving row, and that one can end
    // first. With nothing left to hang from, the index it remembers is what places it, clamped to
    // the end of the list as before.
    const { result, rerender } = renderHook(({ items }) => usePresence(items, keyOf), {
      wrapper: StrictMode,
      initialProps: { items: [row("a"), row("b"), row("c")] },
    });
    rerender({ items: [row("a"), row("c")] });
    rerender({ items: [row("a")] });
    expect(shape(result.current.entries)).toEqual(["a", "b*", "c*"]);
    // `c` was under `b`, and `b` goes first: index 2 of a one-row list clamps to the end.
    act(() => result.current.released("b"));
    expect(shape(result.current.entries)).toEqual(["a", "c*"]);
  });

  it("carries a leaving row with its neighbour when the caller's list reorders under it", () => {
    // The reminder stack only ever loses rows, so index and neighbour agree on every frame of it.
    // The chat switcher re-lists pinned-first and then by recency, so a pin landing inside a row's
    // exit reorders the list around it. By index the row lands between whichever two now hold that
    // ordinal; by neighbour it stays in the gap it actually is.
    const { result, rerender } = renderHook(({ items }) => usePresence(items, keyOf), {
      wrapper: StrictMode,
      initialProps: { items: [row("a"), row("b"), row("c"), row("d")] },
    });
    rerender({ items: [row("a"), row("b"), row("d")] });
    expect(shape(result.current.entries)).toEqual(["a", "b", "c*", "d"]);
    rerender({ items: [row("d"), row("a"), row("b")] });
    expect(shape(result.current.entries)).toEqual(["d", "a", "b", "c*"]);
  });

  it("keeps the first row at the top when it is the one leaving, having nothing to hang from", () => {
    const { result, rerender } = renderHook(({ items }) => usePresence(items, keyOf), {
      wrapper: StrictMode,
      initialProps: { items: [row("a"), row("b")] },
    });
    rerender({ items: [row("b")] });
    expect(shape(result.current.entries)).toEqual(["a*", "b"]);
  });

  it("puts a row that comes back before its exit has ended back into the list", () => {
    // A reminder whose ack never reached the brain is deliverable again on the next summon and
    // arrives carrying the id it left with. Held shut for good, it would be a row that exists,
    // occupies its place in the list, and cannot be seen.
    const { result, rerender } = renderHook(({ items }) => usePresence(items, keyOf), {
      wrapper: StrictMode,
      initialProps: { items: [row("a"), row("b")] },
    });
    rerender({ items: [row("a")] });
    expect(shape(result.current.entries)).toEqual(["a", "b*"]);
    rerender({ items: [row("a"), row("b")] });
    expect(shape(result.current.entries)).toEqual(["a", "b"]);
    // The exit that was interrupted still reports its end; a row back in the caller's list is not
    // the hook's to remove, so the late release is ignored rather than applied.
    act(() => result.current.released("b"));
    expect(shape(result.current.entries)).toEqual(["a", "b"]);
  });

  it("lets new rows arrive while an exit is still running", () => {
    const { result, rerender } = renderHook(({ items }) => usePresence(items, keyOf), {
      wrapper: StrictMode,
      initialProps: { items: [row("a"), row("b"), row("c")] },
    });
    rerender({ items: [row("a"), row("c")] });
    rerender({ items: [row("a"), row("c"), row("d")] });
    expect(shape(result.current.entries)).toEqual(["a", "b*", "c", "d"]);
  });

  it("follows the caller's order, a re-listing being the caller's to order and not this hook's", () => {
    const { result, rerender } = renderHook(({ items }) => usePresence(items, keyOf), {
      wrapper: StrictMode,
      initialProps: { items: [row("a"), row("b")] },
    });
    rerender({ items: [row("b"), row("a")] });
    expect(shape(result.current.entries)).toEqual(["b", "a"]);
  });
});
