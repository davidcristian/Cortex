import { useCallback, useLayoutEffect, useRef, useState } from "react";

// Holding a removed row on screen for the length of its own exit.
//
// `Collapse` gives a section its own height animation, which is what lets the switcher list and the
// reminder stack roll shut instead of vanishing. It cannot do anything for a row INSIDE such a
// section, because React unmounts a removed list item on the spot and an element React has already
// removed cannot be animated: a `Collapse` per row is only half an exit, the row being gone from
// the list that renders the wrapper in the very frame the wrapper would have started rolling.
//
// So the rows are rendered from this list rather than from the caller's. An item that leaves the
// caller's list stays here, marked `leaving`, at the index it held, until the caller says its exit
// has finished. Its neighbours close the gap over that roll instead of snapping over it, because
// the row between them is rolling to nothing rather than being cut out of the layout.
//
// The clock and the curve stay `Collapse`'s. This hook holds no timer and does not know how long an
// exit takes; it is told. That is the whole difference from the reminder stack's first per-row
// exit, which delayed the REMOVAL by `MORPH_ROLL_MS` instead of holding the removed row: the ack
// then rode a timer that an unmount cancelled, so acking a reminder and pressing Ctrl+N inside
// those 300ms sent no ack at all and the reminder came back on the next summon. Nothing the user
// asked for should be waiting on an animation.

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

/** A row that has left the caller's list, with the index it held while it was still in it. */
interface Leaving<T> {
  readonly key: string;
  readonly item: T;
  readonly at: number;
}

/** The caller's list with the leaving rows put back where they were. Ascending index order, so
 *  each insertion is made into the list the one before it already shifted, which is the order the
 *  remembered indices were taken in. An index past the end lands at the end: a row released while
 *  another is still leaving takes its place with it, and the survivor's remembered index is then
 *  one too far. */
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
    entries.splice(Math.min(gone.at, entries.length), 0, {
      key: gone.key,
      item: gone.item,
      leaving: true,
    });
  }
  return entries;
}

/**
 * Render `items` as rows that survive their own removal.
 *
 * The returned `entries` are the caller's items in the caller's order, plus every item that has
 * left since the last render and has not yet been released, each still at the index it held and
 * carrying the last version of itself that was on screen. `released(key)` is what ends an exit,
 * and it is the ONLY thing that does: a row is held for exactly as long as its exit runs.
 *
 * A key that comes back before its exit ends stops leaving, so its `Collapse` reopens and carries
 * on from the height it had rolled to rather than from nothing. That is not a curiosity: a
 * reminder whose ack never reached the brain is deliverable again on the next summon, and it
 * arrives carrying the id it left with.
 *
 * The departure is noticed during the render that lost the item, which is the only place it can be
 * noticed. An effect would paint one frame with the row already deleted, and that frame is the
 * whole defect.
 */
export function usePresence<T>(
  items: readonly T[],
  keyOf: (item: T) => string,
): PresenceList<T> {
  const [leaving, setLeaving] = useState<readonly Leaving<T>[]>([]);
  // What the last COMMIT put on screen, which is what a departure is measured against: the
  // caller's list alone cannot say what has just left it. Written from a layout effect and never
  // during the render, so that rendering stays a pure function of the props, the state and this.
  // Written during the render it was correct in every trace and wrong under `StrictMode`, whose
  // double-invoked render read back what the first pass had just written and concluded that
  // nothing had left: the row was deleted in a frame, which is the exact defect this hook exists
  // to fix, reappearing one layer down.
  const shown = useRef<readonly Presence<T>[]>([]);

  const present = new Set(items.map(keyOf));
  const staying = leaving.filter((gone) => !present.has(gone.key));
  const held = new Set(staying.map((gone) => gone.key));
  // A departure is a row that was on screen as one of the caller's own and is not in the caller's
  // list any more. Rows already leaving are excluded twice over, by the entry's own flag and by
  // `held`: the second is what stops the render that adopts a departure from adopting it again,
  // the commit those flags belong to not having happened yet.
  const departed: Leaving<T>[] = [];
  shown.current.forEach((entry, at) => {
    if (!entry.leaving && !present.has(entry.key) && !held.has(entry.key)) {
      departed.push({ key: entry.key, item: entry.item, at });
    }
  });
  const next = [...staying, ...departed];
  if (departed.length > 0 || staying.length !== leaving.length) {
    // Adjusting state during the render that noticed it, the pattern `Collapse` mounts through:
    // React re-runs this component with the new value before it renders any child, so what is
    // computed below is the same either way and only the state catches up.
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
