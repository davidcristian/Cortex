import { type RefObject, useLayoutEffect, useRef } from "react";

// The panel's size animation. Everything that changes how tall the panel is (a reply arriving,
// the switcher list opening, a reminder showing up, the composer growing a line) eases between
// the old height and the new one instead of jumping.
//
// Why this is code and not a CSS transition: a `transition: height` never fires here, because
// the panel's height is `auto` on both sides and only its *content* changed, which is not a
// computed-value change. `interpolate-size: allow-keywords` does not help either; it makes
// `auto` interpolable against a LENGTH (`height: 0` to `height: auto`), not one content-driven
// `auto` against the next. Measured in a browser before this was written: with the transition
// declared and `interpolate-size` set, opening the switcher moved the panel through exactly one
// distinct height. So the old height is captured before paint and replayed as a real animation.

/** How long a size change takes, and on what curve (matches `--ease` in overlay.css). */
const DURATION_MS = 340;
const EASING = "cubic-bezier(0.4, 0, 0.2, 1)";

/** Below this many pixels a change is not worth animating (a rounding wobble, not a growth). */
const MIN_DELTA_PX = 2;

/**
 * Ease `ref`'s element between its own successive heights.
 *
 * Runs on every render (no dependency list on purpose): the trigger is not one piece of state
 * but any DOM change that resized the element. `useLayoutEffect` reads the new height after the
 * DOM is updated and before the browser paints, so the animation starts from what the eye last
 * saw rather than from the finished layout.
 *
 * **The running animation is cancelled before measuring.** A height animation overrides the used
 * height, so measuring while one runs returns the in-flight value, not the natural one. Reading
 * it anyway is the bug this note exists to prevent: during a stream, every token would animate
 * from in-flight to in-flight, the panel would never converge on its content height, and the
 * text would sit permanently clipped by the panel's `overflow: hidden`. So the order is: read
 * what is displayed, cancel, read the natural height, animate between the two. That also keeps a
 * change mid-ease continuous, because the new animation starts exactly where the old one was.
 *
 * `active` is false while the panel is closed or minimized, where the size is not what moves:
 * the open/close pop and the corner travel are transforms and own that motion themselves.
 * Under `prefers-reduced-motion` nothing is scheduled at all.
 */
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
