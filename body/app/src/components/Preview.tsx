import { useState } from "react";

import { LUCID } from "../edge/edges";
import { PanelEdge } from "./PanelEdge";

interface PreviewProps {
  readonly reply: string;
  readonly onClick: () => void;
  /** Hover pauses the auto-fade (useOverlay); leaving restarts the full countdown. */
  readonly onHover: (hovering: boolean) => void;
}

/** The card shown when a turn completes while the overlay is minimized: the reply and the draining
 *  auto-fade bar, nothing else. The card's appearance is the whole signal, and the bar shows how
 *  long it will stay. Hovering pauses the drain (CSS) and the fade timer with it; on leave both
 *  restart from the top (the bar remounts, keyed, so what it shows always matches the timer).
 *
 *  **It always draws a liquid edge, and always Lucid** (user's call, 2026-07-21), whatever the
 *  window registry is set to. This is the one surface that arrives unprompted, over whatever the
 *  user is working in, and a soft edge is what keeps it from reading as a system notification.
 *  Lucid rather than the picked style, because the two louder styles carry colour, which on a card
 *  that appears unprompted would signal activity that has just finished, and Still would make it
 *  the only hard-edged surface in the overlay. */
export function Preview({ reply, onClick, onHover }: PreviewProps) {
  // Read here rather than passed in as a prop, which is what the Orb does with the same query.
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const [drainRun, setDrainRun] = useState(0);
  const leave = () => {
    setDrainRun((run) => run + 1);
    onHover(false);
  };
  return (
    <button
      className="preview"
      onClick={onClick}
      onMouseEnter={() => onHover(true)}
      onMouseLeave={leave}
      aria-label="Open reply"
      type="button"
    >
      <PanelEdge style={LUCID} working={false} animated={!reduced} idPrefix="preview-edge" />
      <div className="pv-b">{reply}</div>
      <div key={drainRun} className="bar" aria-hidden="true" />
    </button>
  );
}
