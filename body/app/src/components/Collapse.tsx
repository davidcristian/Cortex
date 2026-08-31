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

// A section that rolls open and shut instead of appearing and vanishing.
//
// The defect this exists to fix: React unmounts a removed section immediately, so closing the chat
// switcher deleted its rows in one frame, everything below them snapped up into the gap, and only
// then did the panel ease down to its new height, which read as two motions in the wrong order.
// Fading the section out instead does not help, because an invisible element still takes up its
// space and the snap happens later.
//
// So the section animates its own height, from nothing to its content and back. The panel's height
// is `auto`, so it follows this frame by frame with no animation of its own (`usePanelMotion`
// leaves the height alone while `data-morphing` is set). The panel is anchored by its bottom edge,
// so the result is one movement: the list rolls up, the panel's top edge follows it down, and
// nothing else on screen moves.

interface CollapseProps {
  readonly open: boolean;
  /** Marks a section the panel leaves out when it centres itself: see `.collapse.aside`. */
  readonly aside?: boolean;
  /** Roll open on mount as well, from nothing to the content's height.
   *
   *  A section normally appears at its full height and only animates what happens to it afterwards,
   *  which suits a section mounted with the view it belongs to: the switcher's list rolls open
   *  because the panel opens it, not because it arrived. A section mounted into a list that is
   *  already on screen is the other case, and the switcher's empty line is the one that needs this
   *  flag (`SessionList.tsx`): it takes the place of the last row as that row rolls out, so it has
   *  to grow into the gap on the same clock rather than land in it a frame later.
   *
   *  Read once, at mount, and ignored on every render after, since a section already on screen
   *  cannot arrive again. There is no mirror of this for the closing direction, because the empty
   *  line disappears in the frame a row lands and nothing waits on that removal. */
  readonly enter?: boolean;
  /** Called once a closing roll has finished, which is the moment the content inside may be
   *  removed for good. It lets a list hold a removed row until its own exit ends
   *  (`overlay/usePresence.ts`) without keeping a second copy of this clock. */
  readonly onClosed?: () => void;
  readonly children: ReactNode;
}

export function Collapse({ open, aside = false, enter = false, onClosed, children }: CollapseProps) {
  const ref = useRef<HTMLDivElement>(null);
  // Kept mounted through the closing animation: an exit cannot be animated on an element React
  // has already removed. `rendered` therefore lags `open` on the way out, never on the way in.
  const [rendered, setRendered] = useState(open);
  // Where the roll below treats the section as already standing. A section that is to roll in on
  // mount is recorded here as shut, so the first layout effect finds a change to animate and rolls
  // from nothing to the content, as a later opening would.
  const at = useRef(open && !enter);
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
    // Mid-roll the animation overrides the height, so the displayed value is read before cancelling
    // and the natural one after, which lets a reopened section carry on from where it had rolled
    // to. Both are the used height off the computed style (`heightOf`), which is what the panel
    // reads its own box with, so the roll's target and the panel's prediction of where it leaves
    // the panel are the same measurement. The rect is wrong here, because the panel around this is
    // scaled through a summon and the rect is measured after that transform: at boot the stack
    // rolled to a target 8% short of its content and snapped the last 16px on when the roll ended.
    // `offsetHeight` is wrong too, because it ignores the transform but rounds: an opening roll
    // deliberately does not fill, so a section whose layout height is fractional was returned to
    // its own layout 0.25px from where the keyframes had just painted it, and a closing roll
    // started the same 0.25px above where it had been standing (measured over the demo at 900x1000:
    // the reminder stack's aside stands at 193.75px and rolled to 194).
    const live = running.current !== null && running.current.playState === "running";
    const displayed = live ? heightOf(element) : open ? 0 : null;
    running.current?.cancel();
    running.current = null;
    // A close with nothing to animate commits its collapsed height inline (see below), so hand the
    // height back to layout before asking what the content is worth.
    element.style.height = "";
    const natural = heightOf(element);
    const from = displayed ?? natural;
    const to = open ? natural : 0;
    const finish = () => {
      // A finished closing roll is deliberately kept in `running`: it holds the collapsed height
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
      // Last, and only on the way shut: this call tells the caller it may remove the element, and
      // the panel re-measures on the event above, so the row is still part of what the panel
      // measures. React's batching would hold the caller's removal until after this function
      // returns in either order, so the order here is what the removal is allowed to depend on
      // rather than what makes it work today.
      if (!open) {
        onClosed?.();
      }
    };
    if (
      Math.abs(to - from) < MIN_DELTA_PX ||
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    ) {
      // No animation runs here, so there is no fill to hold the end state: a closing section would
      // stand at full height until React removed it, and the panel measures itself on the event
      // below, so it would be placed around rows that are already gone. Traced under
      // prefers-reduced-motion: closing the chat switcher left the panel 119px lower than it had
      // been before it opened, and it stayed there. Writing the collapsed height by hand does what
      // the forwards fill does on the animated path.
      if (!open) {
        element.style.height = "0px";
      }
      finish();
      return;
    }
    // The panel reads this attribute and leaves the height alone while it is set, so the two do not
    // animate the same pixels against each other. Its value is the height being rolled to: the
    // panel works out from it how tall it is about to be, and takes its own bottom edge off the
    // ceiling over this same roll rather than in a second movement afterwards.
    element.setAttribute(MORPHING_ATTRIBUTE, String(to));
    const animation = element.animate(
      [
        { height: `${from}px`, opacity: open ? 0 : 1 },
        { height: `${to}px`, opacity: open ? 1 : 0 },
      ],
      // A closing roll holds its end state, because unmounting is a React render away: with the
      // default `fill: "none"` the element snapped back to its natural height the instant the
      // animation ended and painted there until React caught up. Traced at 60Hz, that was one
      // frame of the whole switcher reappearing, and the panel measured that frame too. The
      // opening direction must not fill: its end state is the natural height, so there is nothing
      // to hold, and holding it would freeze the section at whatever its content was on open.
      { duration: MORPH_ROLL_MS, easing: EASING, fill: open ? "none" : "forwards" },
    );
    animation.onfinish = finish;
    running.current = animation;
    // The event is dispatched because not every roll is a render the panel sees: the sections in
    // its own chrome open on overlay state and it re-renders with them, but a reply's Thoughts
    // disclosure owns its open state locally and nothing above that message renders when it is
    // clicked.
    //
    // The one ordering constraint on this line is that it comes after the attribute, which is where
    // the target height is published; a listener arriving before it reads a panel with nothing
    // rolling in it. Moved above the `setAttribute`, `Collapse.test.tsx`'s start-event test fails,
    // which is the evidence that this is an ordering rather than a coincidence.
    //
    // Which side of `element.animate` it falls on does not matter, and an earlier version of this
    // comment claimed it did. The panel predicts its coming height as "what it is now, less what
    // this section takes now, plus the target" (`panelRide.ts`), so the section's current height
    // cancels out: measured in Chromium at a 900px viewport, a listener before `animate` reads 464
    // less 76 plus 76, and one after it reads 388 less 0 plus 76, both 464. The two 60Hz traces of
    // the panel are frame for frame identical. It stays here so a listener reads a fully set up
    // roll, and nothing else depends on the position.
    element.dispatchEvent(new CustomEvent(MORPH_START_EVENT, { bubbles: true }));
  });

  return rendered ? (
    <div className={`collapse${aside ? " aside" : ""}`} ref={ref}>
      {children}
    </div>
  ) : null;
}
