import { type RefObject, useLayoutEffect, useRef } from "react";

/** How long a size change takes, and on what curve (matches `--ease` in overlay.css). */
const DURATION_MS = 340;
const EASING = "cubic-bezier(0.4, 0, 0.2, 1)";

/** Below this many pixels a change is not worth animating (a rounding wobble, not a growth). */
const MIN_DELTA_PX = 2;

/** Ease `ref`'s element between its own successive heights. */
export function useGrowthAnimation(ref: RefObject<HTMLElement | null>, active: boolean): void {
  const natural = useRef<number | null>(null);
  const running = useRef<Animation | null>(null);

  useLayoutEffect(() => {
    const element = ref.current;
    if (element === null) {
      return;
    }
    const displayed =
      running.current === null ? natural.current : element.getBoundingClientRect().height;
    running.current?.cancel();
    running.current = null;
    const next = element.getBoundingClientRect().height;
    natural.current = next;
    if (!active || displayed === null || Math.abs(next - displayed) < MIN_DELTA_PX) {
      // Closed, first measurement, or nothing moved: keep the height for next time, animate
      // nothing. Measuring while closed is what lets a reopen animate from a real height.
      return;
    }
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      return;
    }
    running.current = element.animate([{ height: `${displayed}px` }, { height: `${next}px` }], {
      duration: DURATION_MS,
      easing: EASING,
    });
  });
}
