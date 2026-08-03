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

/** A row that has left the caller's list, with where it was standing when it did: the key of the
 *  row directly above it, and the index it held. */
interface Leaving<T> {
  readonly key: string;
  readonly item: T;
  /** The row this one was under, or `null` if it was the first. A gap is between two rows rather
   *  than at an ordinal, and a list that REORDERS is the case that tells the two apart. */
  readonly after: string | null;
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
    const anchor = entries.findIndex((entry) => entry.key === gone.after);
    entries.splice(anchor === -1 ? Math.min(gone.at, entries.length) : anchor + 1, 0, {
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
      // The anchor is read off what was on SCREEN, so it may itself be a row that is leaving. That
      // is the intent: two rows going at once come back as the pair they were, the later one under
      // the earlier one, the ascending sort in `merge` having already put the earlier one back.
      const after = shown.current[at - 1]?.key ?? null;
      departed.push({ key: entry.key, item: entry.item, after, at });
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
