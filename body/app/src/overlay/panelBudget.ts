// The panel's ceiling lives on the element as `max-height`, which a descendant cannot read. The
// two roll-open sections need it: with both full the composer ended up 204px past the clipped edge.

/** The panel's own ceiling, published for the cascade. Read by overlay.css and by nothing else. */
export const CEILING_PROPERTY = "--ceiling";

/** Cap `element` at `ceiling` pixels, and publish the same number for the stylesheet. Every layout
 *  write of the panel's `max-height` goes through here, which is what keeps the two equal. The
 *  keyframes are deliberately left out: an interpolating budget would resize the sections. */
export function capTo(element: HTMLElement, ceiling: number): void {
  element.style.maxHeight = `${ceiling}px`;
  element.style.setProperty(CEILING_PROPERTY, `${ceiling}px`);
}
