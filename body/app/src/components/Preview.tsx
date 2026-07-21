import { useState } from "react";

import { LUCID } from "../edge/edges";
import { PanelEdge } from "./PanelEdge";

interface PreviewProps {
  readonly reply: string;
  readonly onClick: () => void;
  /** Hover pauses the auto-fade (useOverlay); leaving restarts the full countdown. */
  readonly onHover: (hovering: boolean) => void;
}

/** The completed-while-minimized preview card: the reply and the draining auto-fade bar,
 *  nothing else. The card appearing *is* the signal, and the bar says it will go. Hovering
 *  pauses the drain (CSS) and the fade timer with it; on leave both restart from the top
 *  (the bar remounts, keyed, so what it shows always matches the timer).
 *
 *  **It always dreams, and always in Lucid** (user's call, 2026-07-21), whatever the window
 *  registry is set to. The card is the one surface that arrives on its own, over whatever the
 *  user is working in, so a soft edge is what keeps it from reading as a system notification;
 *  and Lucid rather than the picked style because the two louder ones carry colour, which on a
 *  card that appears unbidden would announce activity that has just finished. Still would leave
 *  it the only hard-edged surface in the overlay. */
export function Preview({ reply, onClick, onHover }: PreviewProps) {
  // Read here rather than threaded in, which is the Orb's pattern for the same question.
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
