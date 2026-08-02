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

/** A row that has left the caller's list, with the index it held while it was still in it. */
interface Leaving<T> {
  readonly key: string;
  readonly item: T;
  readonly at: number;
}

/** The caller's list with the leaving rows put back where they were. */
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

/** Render `items` as rows that survive their own removal. */
export function usePresence<T>(
  items: readonly T[],
  keyOf: (item: T) => string,
): PresenceList<T> {
  const [leaving, setLeaving] = useState<readonly Leaving<T>[]>([]);
  const shown = useRef<readonly Presence<T>[]>([]);

  const present = new Set(items.map(keyOf));
  const staying = leaving.filter((gone) => !present.has(gone.key));
  const held = new Set(staying.map((gone) => gone.key));
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
