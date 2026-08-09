
/**
 * Set on the element for as long as it is animating its own height, and holding the height it is
 * animating TO, in px.
 */
export const MORPHING_ATTRIBUTE = "data-morphing";

/**
 * How much SHORTER the view on screen is than the tallest shape it can take, in px, published by a
 * view that has more than one (the console, whose two tabs differ) and read by `panelPlacement`
 * when it places that view.
 */
export const TAB_SLACK_ATTRIBUTE = "data-tab-slack";

/** How long a section's roll takes. */
export const MORPH_ROLL_MS = 300;

/**
 * Dispatched (bubbling) by that element when it starts, and after the attribute above is set: that
 * is where the roll publishes the height it is going to, so a listener arriving first would find
 * nothing rolling at all.
 */
export const MORPH_START_EVENT = "cortex:morphstart";

/** Dispatched (bubbling) by that element when it stops. The panel re-measures on it, because a
 *  section rolling OPEN finishes without a re-render of its own: it changes no React state, so
 *  nothing else would tell the panel it is now taller and may have outgrown its ceiling. */
export const MORPH_END_EVENT = "cortex:morphend";

/** The curve both sides ride (matches `--ease` in overlay.css). */
export const EASING = "cubic-bezier(0.4, 0, 0.2, 1)";

/** Below this many pixels a change is not worth animating: a rounding wobble, not a move. */
export const MIN_DELTA_PX = 2;
