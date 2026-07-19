
/** Set on the element for as long as it is animating its own height. While the panel contains one,
 *  `usePanelMotion` leaves the height alone. */
export const MORPHING_ATTRIBUTE = "data-morphing";

/** Dispatched (bubbling) by that element when it stops. The panel re-measures on it, because a
 *  section rolling OPEN finishes without a re-render of its own: it changes no React state, so
 *  nothing else would tell the panel it is now taller and may have outgrown its ceiling. */
export const MORPH_END_EVENT = "cortex:morphend";
