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
    const { result, rerender } = renderHook(({ items }) => usePresence(items, keyOf), {
      wrapper: StrictMode,
      initialProps: { items: [row("a"), row("b"), row("c")] },
    });
    rerender({ items: [row("a"), row("c")] });
    rerender({ items: [row("a")] });
    expect(shape(result.current.entries)).toEqual(["a", "b*", "c*"]);
    act(() => result.current.released("c"));
    expect(shape(result.current.entries)).toEqual(["a", "b*"]);
    act(() => result.current.released("b"));
    expect(shape(result.current.entries)).toEqual(["a"]);
  });

  it("falls back to the remembered index when the row a leaving row hung from is released first", () => {
    const { result, rerender } = renderHook(({ items }) => usePresence(items, keyOf), {
      wrapper: StrictMode,
      initialProps: { items: [row("a"), row("b"), row("c")] },
    });
    rerender({ items: [row("a"), row("c")] });
    rerender({ items: [row("a")] });
    expect(shape(result.current.entries)).toEqual(["a", "b*", "c*"]);
    act(() => result.current.released("b"));
    expect(shape(result.current.entries)).toEqual(["a", "c*"]);
  });

  it("carries a leaving row with its neighbour when the caller's list reorders under it", () => {
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
    const { result, rerender } = renderHook(({ items }) => usePresence(items, keyOf), {
      wrapper: StrictMode,
      initialProps: { items: [row("a"), row("b")] },
    });
    rerender({ items: [row("a")] });
    expect(shape(result.current.entries)).toEqual(["a", "b*"]);
    rerender({ items: [row("a"), row("b")] });
    expect(shape(result.current.entries)).toEqual(["a", "b"]);
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
