// The contract between the panel and a section that animates its own height.
//
// The panel's height is `auto`, so it follows a section's height animation frame by frame with no
// animation of its own. That only works if the panel keeps its hands off the height while the
// section is moving, and picks its own geometry back up the moment the section stops.
//
// The two constants at the bottom are here for the same reason as the two at the top: both sides
// animate, often at the same time, and a curve or a threshold that disagreed between them would be
// visible. They were declared twice before this, once each side.

/** Set on the element for as long as it is animating its own height, and holding the height it is
 *  animating TO, in px. While the panel contains one, `usePanelMotion` leaves the height alone, but
 *  it reads that number: knowing how tall the section is about to be is what lets the panel work out
 *  how tall IT is about to be, and slide its bottom edge off the ceiling over the same 300ms rather
 *  than as a second beat afterwards. */
export const MORPHING_ATTRIBUTE = "data-morphing";

/** How much SHORTER the view on screen is than the tallest shape it can take, in px, published by
 *  a view that has more than one (the console, whose two tabs differ) and read by `panelPlacement`
 *  when it places that view. It is what lets a multi-shape view be positioned by the shape it
 *  could grow to rather than by the one it happens to open on: the panel sets its top edge as if
 *  the tallest were showing and lets the shorter tab end higher, so the tab strip sits at one
 *  height whichever tab the console is entered on. Absent or "0" means the view is at its tallest. */
export const TAB_SLACK_ATTRIBUTE = "data-tab-slack";

/** How long a section's roll takes. Shared, because the panel's concurrent slide has to land with
 *  it: two movements at different speeds read as two movements. */
export const MORPH_ROLL_MS = 300;

/** Dispatched (bubbling) by that element when it starts, and after the attribute above is set: that
 *  is where the roll publishes the height it is going to, so a listener arriving first would find
 *  nothing rolling at all. Where the dispatch falls relative to the height animation itself is not
 *  part of the contract: the panel's prediction (`panelRide.ts`) cancels the section's current
 *  height out either way, so both orderings reach the same number (`Collapse.tsx` has the two).
 *
 *  A roll is not always a render the panel sees. The sections in the panel's own chrome open and
 *  shut on overlay state, so the panel re-rendered alongside them and its layout effect found the
 *  attribute for free; a reply's Thoughts disclosure owns its open state locally, and nothing above
 *  that message re-renders when it is clicked. Traced at 60Hz before this existed: the trace rolled
 *  open over 300ms with the panel's `auto` height following it, and then the panel, hearing only the
 *  END of the roll and remembering the geometry from before it, snapped back to its old height for
 *  one frame and eased 76px up and 43px down a second time. */
export const MORPH_START_EVENT = "cortex:morphstart";

/** Dispatched (bubbling) by that element when it stops. The panel re-measures on it, because a
 *  section rolling OPEN finishes without a re-render of its own: it changes no React state, so
 *  nothing else would tell the panel it is now taller and may have outgrown its ceiling. */
export const MORPH_END_EVENT = "cortex:morphend";

/** The curve both sides ride (matches `--ease` in overlay.css). */
export const EASING = "cubic-bezier(0.4, 0, 0.2, 1)";

/** Below this many pixels a change is not worth animating: a rounding wobble, not a move. */
export const MIN_DELTA_PX = 2;
