import { useState } from "react";

import { LUCID } from "../edge/edges";
import { PanelEdge } from "./PanelEdge";

interface PreviewProps {
  readonly reply: string;
  readonly onClick: () => void;
  /** Hover pauses the auto-fade (useOverlay); leaving restarts the full countdown. */
  readonly onHover: (hovering: boolean) => void;
}

/** The card shown when a turn completes while the overlay is minimized: the reply and the
 *  draining auto-fade bar. Hovering pauses the drain and the fade timer with it. It always draws a
 *  Lucid edge, whatever the window setting is, so it does not read as a system notification. */
export function Preview({ reply, onClick, onHover }: PreviewProps) {
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
