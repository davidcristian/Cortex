import { useEffect, useState } from "react";

// Which view is on its way out, so it can be drawn while it leaves.
//
// The panel shows one view at a time (the chat, and each of the console's tabs) and morphs between
// them: it resizes to what the incoming view needs and slides back to true centre. That morph has
// nothing to cross-fade against unless the outgoing view is still on screen, and React removes it
// the instant the state changes. So the leaving view is named for a moment longer; the panel keeps
// it mounted, takes it out of the layout flow (it must not define the height the panel is easing
// to), and fades it out over the top of the one arriving.

/**
 * The view being left behind, or null when the panel has settled.
 *
 * Derived during render rather than in an effect: the frame in which `view` changes is exactly the
 * frame the outgoing view has to be taken out of flow, and an effect would be one paint too late.
 */
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
