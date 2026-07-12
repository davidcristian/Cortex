import { useState } from "react";

interface PreviewProps {
  readonly reply: string;
  readonly onClick: () => void;
  /** Hover pauses the auto-fade (useOverlay); leaving restarts the full countdown. */
  readonly onHover: (hovering: boolean) => void;
}

/** The completed-while-minimized preview card: the reply and the draining auto-fade bar,
 *  nothing else. The card appearing *is* the signal, and the bar says it will go. Hovering
 *  pauses the drain (CSS) and the fade timer with it; on leave both restart from the top
 *  (the bar remounts, keyed, so what it shows always matches the timer). */
export function Preview({ reply, onClick, onHover }: PreviewProps) {
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
      <div className="pv-b">{reply}</div>
      <div key={drainRun} className="bar" aria-hidden="true" />
    </button>
  );
}
