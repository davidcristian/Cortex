// The two-part contract between the panel and a section that animates its own height.
//
// The panel's height is `auto`, so it follows a section's height animation frame by frame with no
// animation of its own. That only works if the panel keeps its hands off the height while the
// section is moving, and picks its own geometry back up the moment the section stops.

/** Set on the element for as long as it is animating its own height. While the panel contains one,
 *  `usePanelMotion` leaves the height alone. */
export const MORPHING_ATTRIBUTE = "data-morphing";

/** Dispatched (bubbling) by that element when it stops. The panel re-measures on it, because a
 *  section rolling OPEN finishes without a re-render of its own: it changes no React state, so
 *  nothing else would tell the panel it is now taller and may have outgrown its ceiling. */
export const MORPH_END_EVENT = "cortex:morphend";
