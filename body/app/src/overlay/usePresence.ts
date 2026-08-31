// Holding a removed row on screen for the length of its own exit. React unmounts a removed list
// item on the spot, and an element React has already removed cannot be animated, so the rows are
// rendered from this list rather than from the caller's. The clock and the curve stay `Collapse`'s.

import { useCallback, useLayoutEffect, useRef, useState } from "react";

/** One row to render: the caller's item, and whether it is on its way out. */
export interface Presence<T> {
  readonly key: string;
  readonly item: T;
  /** True while the item has left the caller's list and only its exit is still on screen. */
  readonly leaving: boolean;
}

/** The rows to render, and the way a row reports that its exit has finished. */
export interface PresenceList<T> {
  readonly entries: readonly Presence<T>[];
  /** Drop a leaving row for good. Wire it to the end of that row's own exit animation. */
  readonly released: (key: string) => void;
}

/** A row that has left the caller's list, with where it was when it did: the key of the row
 *  directly above it, and the index it had. */
interface Leaving<T> {
  readonly key: string;
  readonly item: T;
  /** The row this one was under, or `null` if it was the first. A gap is between two rows rather
   *  than at an ordinal, which is what tells the two apart in a list that reorders. */
  readonly after: string | null;
  readonly at: number;
}

/** The caller's list with the leaving rows put back where they were, in ascending index order so
 *  each insertion is made into the list the one before it already shifted. A row goes back under
 *  the row it was under, with the index as the fallback when that neighbour is gone. */
function merge<T>(
  items: readonly T[],
  keyOf: (item: T) => string,
  leaving: readonly Leaving<T>[],
): Presence<T>[] {
  const entries: Presence<T>[] = items.map((item) => ({
    key: keyOf(item),
    item,
    leaving: false,
  }));
  for (const gone of [...leaving].sort((a, b) => a.at - b.at)) {
    const anchor = entries.findIndex((entry) => entry.key === gone.after);
    entries.splice(anchor === -1 ? Math.min(gone.at, entries.length) : anchor + 1, 0, {
      key: gone.key,
      item: gone.item,
      leaving: true,
    });
  }
  return entries;
}

/** Render `items` as rows that survive their own removal: the caller's items in the caller's
 *  order, plus every item that has left and not yet been released, each still in the gap it left.
 *  A key that comes back before its exit ends stops leaving, and its `Collapse` reopens. */
export function usePresence<T>(
  items: readonly T[],
  keyOf: (item: T) => string,
): PresenceList<T> {
  const [leaving, setLeaving] = useState<readonly Leaving<T>[]>([]);
  // What the last commit put on screen, which is what a departure is measured against. Written
  // from a layout effect and never during the render: written during the render, `StrictMode`'s
  // double-invoked pass read back what the first pass wrote and concluded nothing had left.
  const shown = useRef<readonly Presence<T>[]>([]);

  const present = new Set(items.map(keyOf));
  const staying = leaving.filter((gone) => !present.has(gone.key));
  const held = new Set(staying.map((gone) => gone.key));
  // A departure is a row that was on screen as one of the caller's own and is not in the caller's
  // list any more. `held` stops the render that adopts a departure from adopting it twice.
  const departed: Leaving<T>[] = [];
  shown.current.forEach((entry, at) => {
    if (!entry.leaving && !present.has(entry.key) && !held.has(entry.key)) {
      // The anchor is read off what was on screen, so it may itself be a row that is leaving, and
      // two rows going at once come back as the pair they were.
      const after = shown.current[at - 1]?.key ?? null;
      departed.push({ key: entry.key, item: entry.item, after, at });
    }
  });
  const next = [...staying, ...departed];
  if (departed.length > 0 || staying.length !== leaving.length) {
    // Adjusting state during the render that noticed it, the pattern `Collapse` mounts through:
    // React re-runs this component with the new value before it renders any child.
    setLeaving(next);
  }
  const entries = merge(items, keyOf, next);
  useLayoutEffect(() => {
    shown.current = entries;
  });

  const released = useCallback((key: string) => {
    setLeaving((current) => current.filter((gone) => gone.key !== key));
  }, []);

  return { entries, released };
}
