import { type ReactNode, useLayoutEffect, useRef, useState } from "react";

import {
  EASING,
  MIN_DELTA_PX,
  MORPHING_ATTRIBUTE,
  MORPH_END_EVENT,
  MORPH_ROLL_MS,
  MORPH_START_EVENT,
} from "../overlay/morph";

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
    const live = running.current !== null && running.current.playState === "running";
    const displayed = live ? element.offsetHeight : open ? 0 : null;
    running.current?.cancel();
    running.current = null;
    // A close with nothing to animate commits its collapsed height inline (see below), so hand the
    // height back to layout before asking what the content is worth.
    element.style.height = "";
    const natural = element.offsetHeight;
    const from = displayed ?? natural;
    const to = open ? natural : 0;
    const finish = () => {
      // A finished CLOSING roll is deliberately kept in `running`: it holds the collapsed height
      // (see the `fill` below), and this reference is what a reopen cancels to get the natural
      // height back, in the one case where React never removed the element in between.
      if (open) {
        running.current = null;
      }
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
      if (!open) {
        element.style.height = "0px";
      }
      finish();
      return;
    }
    element.setAttribute(MORPHING_ATTRIBUTE, String(to));
    const animation = element.animate(
      [
        { height: `${from}px`, opacity: open ? 0 : 1 },
        { height: `${to}px`, opacity: open ? 1 : 0 },
      ],
      { duration: MORPH_ROLL_MS, easing: EASING, fill: open ? "none" : "forwards" },
    );
    animation.onfinish = finish;
    running.current = animation;
    element.dispatchEvent(new CustomEvent(MORPH_START_EVENT, { bubbles: true }));
  });

  return rendered ? (
    <div className="collapse" ref={ref}>
      {children}
    </div>
  ) : null;
}
