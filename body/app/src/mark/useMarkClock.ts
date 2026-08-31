import { useEffect, useState } from "react";

// The mark's clock: elapsed seconds since the mark mounted, advanced once per animation frame.
// The bubble's whole motion is a function of this number, so freezing it is all reduced motion
// needs: no frames are scheduled and the shape holds the pose below.

/** The frozen pose. Non-zero so a ping-enveloped mark rests mid ripple rather than at its crest. */
export const STILL_SECONDS = 0.35;

/** Elapsed seconds while `animated`, else the frozen pose. */
export function useMarkClock(animated: boolean): number {
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    if (!animated) {
      return undefined;
    }
    let start: number | null = null;
    let frame = requestAnimationFrame(function step(now: number) {
      start ??= now;
      setSeconds((now - start) / 1000);
      frame = requestAnimationFrame(step);
    });
    return () => cancelAnimationFrame(frame);
  }, [animated]);

  return animated ? seconds : STILL_SECONDS;
}
