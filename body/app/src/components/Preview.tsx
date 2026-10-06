import { useState } from "react";

import { LUCID } from "../edge/edges";
import { PanelEdge } from "./PanelEdge";

interface PreviewProps {
  readonly reply: string;
  /** The tool a pending approval would run, or null when nothing waits to be approved. */
  readonly approval: string | null;
  /** Why the turn failed, shown in place of its reply, or null when it did not fail. */
  readonly error: string | null;
  /** Whether the auto-fade runs (`previewStays` is false); the bar shows it. */
  readonly fading: boolean;
  readonly onClick: () => void;
  /** Hover pauses the auto-fade (useOverlay); leaving restarts the full countdown. */
  readonly onHover: (hovering: boolean) => void;
}

/** The card shown when a turn ends or asks for approval while the overlay is minimized: the
 *  reply, its error or the waiting approval, and the draining bar while the fade runs. It always
 *  draws a Lucid edge, so it does not read as a system notification. */
export function Preview({ reply, approval, error, fading, onClick, onHover }: PreviewProps) {
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
      aria-label={approval === null ? "Open reply" : "Open the approval"}
      type="button"
    >
      <PanelEdge style={LUCID} working={false} animated={!reduced} idPrefix="preview-edge" />
      <div className="pv-b">
        {approval === null ? (error ?? reply) : `Waiting for your approval to run ${approval}`}
      </div>
      {fading ? <div key={drainRun} className="bar" aria-hidden="true" /> : null}
    </button>
  );
}
