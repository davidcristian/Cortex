import { type ReactNode, useLayoutEffect, useRef, useState } from "react";

import { MORPHING_ATTRIBUTE, MORPH_END_EVENT } from "../overlay/morph";

/** How long the roll takes, and on what curve (matches `--ease` in overlay.css). */
const DURATION_MS = 300;
const EASING = "cubic-bezier(0.4, 0, 0.2, 1)";

/** Below this many pixels there is nothing to see; apply the end state and skip the animation. */
const MIN_DELTA_PX = 2;

interface CollapseProps {
  readonly open: boolean;
  readonly children: ReactNode;
}

export function Collapse({ open, children }: CollapseProps) {
  const ref = useRef<HTMLDivElement>(null);
  // Kept mounted through the closing animation: an exit cannot be animated on an element React
  // has already removed. `rendered` therefore lags `open` on the way out, never on the way in.
  const [rendered, setRendered] = useState(open);
  const at = useRef(open);
  const running = useRef<Animation | null>(null);

  if (open && !rendered) {
    // Mount now, in this same render, so the layout effect below can measure the real content
    // height before the browser paints and start the roll from zero.
    setRendered(true);
  }

  useLayoutEffect(() => {
    const element = ref.current;
    if (element === null || at.current === open) {
      return;
    }
    at.current = open;
    // Mid-roll the animation overrides the height, so read the displayed value BEFORE cancelling
    // and the natural one after: a reopened section carries on from where it had rolled to.
    const live = running.current !== null && running.current.playState === "running";
    const displayed = live ? element.getBoundingClientRect().height : open ? 0 : null;
    running.current?.cancel();
    running.current = null;
    const natural = element.getBoundingClientRect().height;
    const from = displayed ?? natural;
    const to = open ? natural : 0;
    const finish = () => {
      running.current = null;
      element.removeAttribute(MORPHING_ATTRIBUTE);
      if (!open) {
        setRendered(false);
      }
      // Rolling open changes no state, so nothing else would tell the panel it just got taller
      // and may have grown past the clear space it keeps above itself.
      element.dispatchEvent(new CustomEvent(MORPH_END_EVENT, { bubbles: true }));
    };
    if (
      Math.abs(to - from) < MIN_DELTA_PX ||
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    ) {
      finish();
      return;
    }
    // The panel reads this attribute and leaves the height alone while it is set, so the two do
    // not animate the same pixels against each other.
    element.setAttribute(MORPHING_ATTRIBUTE, "");
    const animation = element.animate(
      [
        { height: `${from}px`, opacity: open ? 0 : 1 },
        { height: `${to}px`, opacity: open ? 1 : 0 },
      ],
      { duration: DURATION_MS, easing: EASING },
    );
    animation.onfinish = finish;
    running.current = animation;
  });

  return rendered ? (
    <div className="collapse" ref={ref}>
      {children}
    </div>
  ) : null;
}
