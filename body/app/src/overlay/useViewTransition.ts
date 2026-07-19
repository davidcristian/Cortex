// Which view is on its way out, so it can be drawn while it leaves. The panel's morph has nothing
// to cross-fade against unless the outgoing view is still on screen, and React removes it the
// instant the state changes, so it is named for a moment longer.

import { useEffect, useState } from "react";

/** The view being left behind, or null when the panel has settled. Derived during render rather
 *  than in an effect, because the frame `view` changes in is exactly the frame the outgoing view
 *  has to leave the layout flow. */
export function useViewTransition(view: string, durationMs: number): string | null {
  const [settled, setSettled] = useState(view);

  useEffect(() => {
    if (settled === view) {
      return;
    }
    const timer = setTimeout(() => setSettled(view), durationMs);
    return () => clearTimeout(timer);
  }, [settled, view, durationMs]);

  return settled === view ? null : settled;
}
