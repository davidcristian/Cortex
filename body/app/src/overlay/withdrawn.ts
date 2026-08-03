// `aria-hidden` hides a subtree from assistive technology and leaves the tab order alone; `inert`
// takes it out of the tab order, out of the pointer's reach and out of the accessibility tree, and
// blurs whatever had focus inside it. Both are written together, so one call says the whole fact.

declare module "react" {
  interface HTMLAttributes<T> {
    /** Present (`""`) or absent. React 18.3.1 has no prop entry for `inert`, so it goes through
     *  the custom-attribute path: `inert=""` renders the attribute and `inert={true}` is dropped
     *  with a warning. Narrowed to the empty string so no call site can write the dropped form. */
    inert?: "";
  }
}

/** The attributes that say a subtree is not part of the page right now. Spread onto the element
 *  whose whole subtree is going away, never onto a leaf inside one. */
export interface Withdrawn {
  readonly "aria-hidden": boolean;
  readonly inert?: "";
}

/** A subtree that is neither announced nor reachable, or one that is both. `aria-hidden` is
 *  written in both directions; `inert` in one, because the attribute is boolean in the HTML sense,
 *  so its absence is its false and `inert="false"` would be an inert element. */
export function withdrawn(away: boolean): Withdrawn {
  return away ? { "aria-hidden": true, inert: "" } : { "aria-hidden": false };
}
