// Taking a subtree out of the page is one fact, so it is written once.
//
// The overlay keeps things mounted that are not currently the thing on screen: the chat while the
// console is up, the console for the length of the morph it spends leaving, the tab not showing
// inside the console, and the whole panel while it is dismissed. Every one of those was
// `aria-hidden` and none of them was untabbable, so a screen reader was told the truth and the tab
// key was not: pressing Tab during a crossing walked into a pane that was fading out, and pressing
// it on a dismissed panel walked through an invisible one.
//
// `aria-hidden` cannot fix that on its own, and it is worth being clear about why, because the two
// attributes are not two spellings of one idea. `aria-hidden` hides a subtree from assistive
// technology and leaves the tab order alone, and a browser ignores it on an ancestor of the focused
// element, so the app has to move focus first for it to do anything at all. `inert` carries both
// halves: it takes the subtree out of the tab order, out of the pointer's reach and out of the
// accessibility tree, and it blurs whatever inside it had focus. It is also newer, so `aria-hidden`
// stays beside it as the attribute every reader already understands.

// What React 18 can and cannot do with `inert`, measured rather than assumed.
//
// The refinement this closes recorded `inert` as wanting React 19. Only the ergonomics do. React 19
// added `inert` to its prop tables as a boolean; React 18.3.1 has no entry for it, so it falls
// through to the custom-attribute path, which writes a string value straight to the DOM and drops a
// boolean one with a console warning. Probed against the tree's own react-dom 18.3.1, server and
// client: `inert={true}` renders `<div></div>` and warns, `inert=""` renders `<div inert="">` and
// does not, `inert={undefined}` removes the attribute again. An empty string is how HTML spells a
// boolean attribute that is present, so the string form is the real thing, written the way the
// platform writes it.
//
// What React 18 genuinely lacks is the type, so the one declaration below adds it, narrowed to the
// empty string rather than opened to `boolean` so no call site can write the form React 18 drops.
// When this tree moves to React 19 the augmentation is what to delete, and `Withdrawn` can widen
// its field to `boolean` with nothing else changing.
declare module "react" {
  interface HTMLAttributes<T> {
    /** Present (`""`) or absent. React 18 drops a boolean `inert`; see the note above. */
    inert?: "";
  }
}

/** The attributes that say a subtree is not part of the page right now. Spread onto the element
 *  whose whole subtree is going away, never onto a leaf inside one. */
export interface Withdrawn {
  readonly "aria-hidden": boolean;
  readonly inert?: "";
}

/**
 * A subtree that is neither announced nor reachable, or one that is both.
 *
 * `aria-hidden` is written in both directions, because it was already written in both directions
 * and an explicit `aria-hidden="false"` on the live view is a useful thing for the tree to say.
 * `inert` is written in one: the attribute is boolean in the HTML sense, so its absence is its
 * false, and `inert="false"` would be an inert element.
 */
export function withdrawn(away: boolean): Withdrawn {
  return away ? { "aria-hidden": true, inert: "" } : { "aria-hidden": false };
}
