// The cap the panel is standing under, written where the cascade can spend it.
//
// The panel's ceiling is worked out in `panelGeometry` and lives on the element as `max-height`, and
// `max-height` is the one thing a descendant cannot read: CSS has no way to ask an ancestor how tall
// it is allowed to be. The two roll-open sections in the panel's chrome need exactly that answer,
// because their own caps were each written as if that section were alone with the panel, and two
// sections that are both at a cap written that way outrun the panel between them. Measured in
// Chromium at the body's own 640x720 window with the demo's two chats and three reminders: opening
// the chat switcher put the hint strip 29.75px past the panel's clipped edge, and with both sections
// full it was 246px past it with the composer 204px past it, which is the send button and every
// shortcut off screen at once.
//
// So the ceiling is published as a custom property beside the `max-height` it always equals, and
// overlay.css subtracts the furniture the panel keeps for itself (the header, the composer at its
// floor, the hint strip, the history's own padding) to get what the sections may share. One write,
// two readers, and no second source: a placement cannot cap the panel at one height and the sections
// at another, because the number is the same number.
//
// This is not a new input to `panelWatch`. The property is only ever written from inside `place`,
// which the watch already brackets by dropping its observation for the frame the panel is written
// in, so the section resize this causes lands in that same frame and is answered by the placement
// that caused it rather than by a second one.

/** The panel's own ceiling, published for the cascade. Read by overlay.css and by nothing else. */
export const CEILING_PROPERTY = "--ceiling";

/**
 * Cap `element` at `ceiling` pixels, and say so where the stylesheet can hear it.
 *
 * Every layout write of the panel's `max-height` goes through here, which is what keeps the two
 * numbers equal. The keyframes are deliberately not routed through it: a move carries its ceiling
 * along so the cap is never tighter than the height it is clamping (`panelGeometry.frame`), but that
 * cap is a visual override on the way to a destination whose layout is already settled, and handing
 * the sections an interpolating budget would resize them once a frame for the length of every move.
 */
export function capTo(element: HTMLElement, ceiling: number): void {
  element.style.maxHeight = `${ceiling}px`;
  element.style.setProperty(CEILING_PROPERTY, `${ceiling}px`);
}
