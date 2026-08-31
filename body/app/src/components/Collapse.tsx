import { type ReactNode, useLayoutEffect, useRef, useState } from "react";

import {
  EASING,
  MIN_DELTA_PX,
  MORPHING_ATTRIBUTE,
  MORPH_END_EVENT,
  MORPH_ROLL_MS,
  MORPH_START_EVENT,
} from "../overlay/morph";
import { heightOf } from "../overlay/panelMemory";

// A section that rolls open and shut by animating its own height. React removes a closed section
// at once, so without this its rows vanished in one frame and the panel only then eased down after
// them. The panel's own height is `auto`, so it follows this roll frame by frame.

interface CollapseProps {
  readonly open: boolean;
  /** Marks a section the panel leaves out when it centres itself: see `.collapse.aside`. */
  readonly aside?: boolean;
  /** Roll open on mount as well, from nothing to the content's height. Read once at mount and
   *  ignored on every render after. */
  readonly enter?: boolean;
  /** Called once a closing roll has finished, which is the moment the content inside may be removed
   *  for good. */
  readonly onClosed?: () => void;
  readonly children: ReactNode;
}

export function Collapse({ open, aside = false, enter = false, onClosed, children }: CollapseProps) {
  const ref = useRef<HTMLDivElement>(null);
  // Kept mounted through the closing roll: an exit cannot be animated on an element React has
  // already removed, so `rendered` lags `open` on the way out but never on the way in.
  const [rendered, setRendered] = useState(open);
  // The height the next roll starts from. A section that rolls in on mount is recorded here as
  // shut, so the first layout effect finds a change to animate.
  const at = useRef(open && !enter);
  const running = useRef<Animation | null>(null);

  if (open && !rendered) {
    // Mount in this same render, so the layout effect below can measure the real content height
    // before the browser paints.
    setRendered(true);
  }

  useLayoutEffect(() => {
    const element = ref.current;
    if (element === null || at.current === open) {
      return;
    }
    at.current = open;
    // Both heights come from the computed style, which is what the panel measures itself with.
    // `getBoundingClientRect` is wrong here because the panel is scaled during a summon, and
    // `offsetHeight` is wrong because it rounds: a section 193.75px tall rolled to 194.
    const live = running.current !== null && running.current.playState === "running";
    const displayed = live ? heightOf(element) : open ? 0 : null;
    running.current?.cancel();
    running.current = null;
    // A close with nothing to animate writes its collapsed height inline, so hand the height back
    // to layout before asking what the content is worth.
    element.style.height = "";
    const natural = heightOf(element);
    const from = displayed ?? natural;
    const to = open ? natural : 0;
    const finish = () => {
      // A finished closing roll stays in `running`, because its forwards fill is what holds the
      // collapsed height, and a reopen cancels this animation to get the natural height back.
      if (open) {
        running.current = null;
      }
      element.removeAttribute(MORPHING_ATTRIBUTE);
      if (!open) {
        setRendered(false);
      }
      // Rolling open changes no state, so nothing else would tell the panel it just got taller.
      element.dispatchEvent(new CustomEvent(MORPH_END_EVENT, { bubbles: true }));
      // Last, and only on the way shut: the caller may remove the element once this returns, and
      // the panel re-measures on the event above, so the row must still be there for it.
      if (!open) {
        onClosed?.();
      }
    };
    if (
      Math.abs(to - from) < MIN_DELTA_PX ||
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    ) {
      // No animation runs here, so there is no forwards fill to hold the end state and a closing
      // section would stand at full height until React removed it. Under prefers-reduced-motion
      // that left the panel 119px lower than it had been before the switcher opened.
      if (!open) {
        element.style.height = "0px";
      }
      finish();
      return;
    }
    // The panel reads this attribute and leaves its own height alone while it is set, so the two
    // do not animate the same pixels against each other. Its value is the height being rolled to.
    element.setAttribute(MORPHING_ATTRIBUTE, String(to));
    const animation = element.animate(
      [
        { height: `${from}px`, opacity: open ? 0 : 1 },
        { height: `${to}px`, opacity: open ? 1 : 0 },
      ],
      // A closing roll holds its end state, because unmounting is a React render away and with no
      // fill the element snapped back to its natural height for one frame. An opening roll must
      // not fill, or the section would freeze at whatever its content was when it opened.
      { duration: MORPH_ROLL_MS, easing: EASING, fill: open ? "none" : "forwards" },
    );
    animation.onfinish = finish;
    running.current = animation;
    // After the attribute, not before: a listener that arrives first reads a panel with nothing
    // rolling in it, and moving this line above `setAttribute` fails the start-event test.
    element.dispatchEvent(new CustomEvent(MORPH_START_EVENT, { bubbles: true }));
  });

  return rendered ? (
    <div className={`collapse${aside ? " aside" : ""}`} ref={ref}>
      {children}
    </div>
  ) : null;
}
