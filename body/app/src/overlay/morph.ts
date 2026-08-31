/** Set on the element for as long as it is animating its own height, and holding the height it is
 *  animating to, in px. The panel's height is `auto`, so it follows that animation frame by frame,
 *  and `usePanelMotion` reads this number to move its own bottom edge over the same 300ms. */
export const MORPHING_ATTRIBUTE = "data-morphing";

/** How much shorter the view on screen is than the tallest shape it can take, in px, published by
 *  a view that has more than one (the console, whose two tabs differ) and read by `panelPlacement`.
 *  Absent or "0" means the view is at its tallest. */
export const TAB_SLACK_ATTRIBUTE = "data-tab-slack";

/** How long a section's roll takes. Shared, because the panel's own slide has to finish with it:
 *  two movements at different speeds read as two movements. overlay.css restates it as the
 *  `--roll` custom property for the two rules that move along with a roll. */
export const MORPH_ROLL_MS = 300;

/** Dispatched (bubbling) by that element when it starts, and after the attribute above is set,
 *  which is where the roll publishes the height it is going to. A roll is not always a render the
 *  panel sees: a reply's Thoughts disclosure owns its open state locally. */
export const MORPH_START_EVENT = "cortex:morphstart";

/** Dispatched (bubbling) by that element when it stops. The panel re-measures on it, because a
 *  section rolling open changes no React state and nothing else would say it is now taller. */
export const MORPH_END_EVENT = "cortex:morphend";

/** The curve both sides animate on (matches `--ease` in overlay.css). */
export const EASING = "cubic-bezier(0.4, 0, 0.2, 1)";

/** Below this many pixels a change is not worth animating: a rounding wobble, not a move. */
export const MIN_DELTA_PX = 2;
